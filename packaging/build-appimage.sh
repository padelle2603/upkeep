#!/bin/bash
# Build a portable Upkeep AppImage.
#
# What goes in: CPython, PyGObject, GTK3, the typelibs Upkeep actually uses.
# What does NOT: every icon theme and every locale on the build machine.
# PyInstaller happily copies whatever /usr/share holds — on a desktop with
# Papirus and breeze installed that is ~520 MB of icons on its own. We keep
# Adwaita (GTK's built-in fallback, 15 MB) and let anything else fall back to
# it, then bake: 670 MB of freeze -> ~90 MB of AppImage.
#
# Usage: ./packaging/build-appimage.sh [VERSION]
# Needs: pyinstaller, plus appimagetool (or linuxdeploy) to bake.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

VERSION="${1:-$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)}"
ARCH="${ARCH:-x86_64}"
APPDIR="${APPDIR:-AppDir}"
OUT="Upkeep-v${VERSION}-${ARCH}.AppImage"
BUNDLE="${BUNDLE:-build/appimage}"
KEEP_THEME="${KEEP_THEME:-Adwaita}"

command -v pyinstaller >/dev/null 2>&1 || { echo "pip install pyinstaller" >&2; exit 1; }

echo "==> Freezing Upkeep ${VERSION} (Python + PyGObject + GTK3)..."
rm -rf "${APPDIR}" "${BUNDLE}"
pyinstaller \
    --noconfirm --clean --onedir \
    --name upkeep \
    --distpath "${BUNDLE}" \
    --workpath "${BUNDLE}/work" \
    --specpath "${BUNDLE}" \
    --paths src \
    --add-data "$PWD/icons:icons" \
    --hidden-import upkeep.gui.main_window \
    --hidden-import upkeep.gui.app_dialog \
    --hidden-import upkeep.gui.settings_dialog \
    packaging/appimage_entry.py

echo "==> Pruning icon themes and locales..."
SHARE="${BUNDLE}/upkeep/_internal/share"
# Every theme on the build machine gets copied in. Keep only the fallback.
if [ -d "${SHARE}/icons" ]; then
    find "${SHARE}/icons" -mindepth 1 -maxdepth 1 ! -name "${KEEP_THEME}" -exec rm -rf {} +
fi
# Same for translations: one language is one language.
if [ -d "${SHARE}/locale" ]; then
    find "${SHARE}/locale" -mindepth 1 -maxdepth 1 ! -name en -exec rm -rf {} +
fi

echo "==> Assembling ${APPDIR}..."
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/icons/hicolor/scalable/apps" \
         "${APPDIR}/usr/share/doc/upkeep"
cp -r "${BUNDLE}/upkeep"/* "${APPDIR}/usr/bin/"

# The GUI looks for icons/upkeep.svg relative to the package; inside the
# AppImage that resolves through $APPDIR, which AppRun exports.
cp icons/upkeep.svg "${APPDIR}/usr/share/icons/hicolor/scalable/apps/upkeep.svg"
rsvg-convert -w 256 -h 256 -o "${APPDIR}/upkeep.png" icons/upkeep.svg 2>/dev/null \
    || cp icons/upkeep.svg "${APPDIR}/upkeep.png"
cp packaging/upkeep.desktop "${APPDIR}/upkeep.desktop"
cp README.md LEGAL.md PRIVACY.md "${APPDIR}/usr/share/doc/upkeep/"

# The CA store ships with the app. The frozen libcrypto cannot be relied on to
# find the host's: with it missing, TLS verification fails with "unable to get
# local issuer certificate" and the release check reports itself as offline.
# Upkeep is an updater, so a bundle that cannot verify TLS is useless.
CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
[ -f "$CA_BUNDLE" ] || CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
[ -f "$CA_BUNDLE" ] || { echo "no CA bundle found; the AppImage would fail TLS" >&2; exit 1; }
mkdir -p "${APPDIR}/usr/share/ca-certificates"
cp "$CA_BUNDLE" "${APPDIR}/usr/share/ca-certificates/ca-certificates.crt"

cat > "${APPDIR}/AppRun" <<'RUNNER'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="$HERE"
export SSL_CERT_FILE="$HERE/usr/share/ca-certificates/ca-certificates.crt"
export GIT_SSL_CAINFO="$SSL_CERT_FILE"
exec "$HERE/usr/bin/upkeep" "$@"
RUNNER
chmod +x "${APPDIR}/AppRun" "${APPDIR}/usr/bin/upkeep"

echo "==> Smoke test..."
"${APPDIR}/AppRun" --help >/dev/null
# `self` exits 0 (current), 10 (newer release) or 1 (no release yet / offline).
# Until the first release exists, 1 is the normal answer — only a crash is a bug.
"${APPDIR}/AppRun" self || [ $? -le 10 ]

echo "==> Baking ${OUT}..."
if command -v appimagetool >/dev/null 2>&1; then
    ARCH="${ARCH}" appimagetool "${APPDIR}" "${OUT}"
else
    command -v linuxdeploy >/dev/null 2>&1 || {
        echo "need appimagetool (https://github.com/AppImage/appimagetool) or linuxdeploy" >&2
        exit 1
    }
    OUTPUT="${OUT}" linuxdeploy --appdir "${APPDIR}" --output appimage
fi

echo "==> Done: ${OUT}"
ls -la "${OUT}"