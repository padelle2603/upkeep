#!/bin/bash
# Copyright (C) 2026 padelle2603
# SPDX-License-Identifier: GPL-3.0-or-later
set -e

SRC="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${HOME}/.local"
LIBDIR="${PREFIX}/lib/upkeep"
BINDIR="${PREFIX}/bin"
APPDIR="${PREFIX}/share/applications"
ICONDIR="${PREFIX}/share/icons/hicolor"

echo "Installing Upkeep in ${LIBDIR}"
mkdir -p "${LIBDIR}" "${BINDIR}" "${APPDIR}"

# Copy sources (bin, src, tests, README) keeping the structure
cp -r "${SRC}/bin" "${SRC}/src" "${SRC}/tests" "${LIBDIR}/" 2>/dev/null || cp -r "${SRC}/bin" "${SRC}/src" "${LIBDIR}/"
[ -f "${SRC}/README.md" ] && cp "${SRC}/README.md" "${LIBDIR}/"

# CLI launcher
cat > "${BINDIR}/upkeep" <<EOF
#!/usr/bin/env python3
import sys
sys.path.insert(0, "${LIBDIR}/src")
from upkeep.cli import main
sys.exit(main())
EOF
chmod +x "${BINDIR}/upkeep"

# GUI launcher
cat > "${BINDIR}/upkeep-gui" <<EOF
#!/usr/bin/env python3
import sys
sys.path.insert(0, "${LIBDIR}/src")
from upkeep.gui.main_window import run
run()
EOF
chmod +x "${BINDIR}/upkeep-gui"

# Menu entry
cat > "${APPDIR}/upkeep.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Upkeep
Comment=Automatically update AppImages from GitHub
Exec=${BINDIR}/upkeep-gui
Icon=upkeep
Terminal=false
Categories=System;Utility;
Keywords=appimage;update;
EOF

# Icon: scalable SVG + PNG at various resolutions
ICON_SRC="${SRC}/icons/upkeep.svg"
if [ -f "${ICON_SRC}" ]; then
    mkdir -p "${ICONDIR}/scalable/apps"
    cp "${ICON_SRC}" "${ICONDIR}/scalable/apps/upkeep.svg"
    if command -v rsvg-convert >/dev/null 2>&1; then
        RENDER="rsvg-convert"
    elif command -v convert >/dev/null 2>&1; then
        RENDER="convert"
    else
        RENDER=""
        echo "Warning: neither rsvg-convert nor ImageMagick 'convert' found; installing SVG icon only."
    fi
    for size in 48 128 256 512; do
        mkdir -p "${ICONDIR}/${size}x${size}/apps"
        if [ "${RENDER}" = "rsvg-convert" ]; then
            rsvg-convert -w "${size}" -h "${size}" -o "${ICONDIR}/${size}x${size}/apps/upkeep.png" "${ICON_SRC}" \
                || echo "Warning: failed to render ${size}x${size} icon."
        elif [ "${RENDER}" = "convert" ]; then
            convert -background none "${ICON_SRC}" -resize "${size}x${size}" "${ICONDIR}/${size}x${size}/apps/upkeep.png" \
                || echo "Warning: failed to render ${size}x${size} icon."
        fi
    done
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -q "${PREFIX}/share/icons/hicolor" 2>/dev/null || true
    fi
fi

mkdir -p "${HOME}/.config/upkeep"
if [ ! -f "${HOME}/.config/upkeep/config.json" ]; then
    cat > "${HOME}/.config/upkeep/config.json" <<EOF
{
  "settings": {
    "default_install_dir": "~/.local/share/applications/Appimages",
    "tracker_dir": "~/.cache",
    "default_arch": "x86_64",
    "check_on_startup": true,
    "confirm_download": true,
    "create_desktop": true
  },
  "apps": []
}
EOF
fi

echo "Done."
echo "   CLI: ${BINDIR}/upkeep  (try: upkeep --help)"
echo "   GUI: ${BINDIR}/upkeep-gui"
