#!/bin/bash
# Copyright (C) 2026 padelle2603
# SPDX-License-Identifier: GPL-3.0-or-later
set -e

VERBOSE=0
for arg in "$@"; do
    case "$arg" in
        --verbose) VERBOSE=1 ;;
    esac
done
_vlog()  { if [ "$VERBOSE" -eq 1 ]; then echo "  $1"; fi; }

PREFIX="${HOME}/.local"
BINDIR="${PREFIX}/bin"
LIBDIR="${PREFIX}/lib/upkeep"
APPDIR="${PREFIX}/share/applications"
ICONDIR="${PREFIX}/share/icons/hicolor"
CONFIGDIR="${HOME}/.config/upkeep"
TRACKER_GLOB="${HOME}/.cache/appimage_tracker_*.txt"

echo "Upkeep - Uninstallation"

rm -f "${BINDIR}/upkeep"
rm -f "${BINDIR}/upkeep-gui"
rm -rf "${LIBDIR}"

rm -f "${APPDIR}/upkeep.desktop"
# Remove the per-app .desktop entries created for managed AppImages
while IFS= read -r f; do
    rm -f "${f}"
    _vlog "removed ${f}"
done < <(grep -l "managed by Upkeep" "${APPDIR}"/*.desktop 2>/dev/null || true)

rm -rf "${ICONDIR}/scalable/apps/upkeep.svg"
for size in 48 128 256 512; do
    rm -f "${ICONDIR}/${size}x${size}/apps/upkeep.png"
done

if [ -d "${CONFIGDIR}" ]; then
    echo ""
    read -r -p "Remove the configuration folder ${CONFIGDIR}? [y/N] " ans
    if [ "$(echo "${ans}" | tr '[:upper:]' '[:lower:]')" = "y" ]; then
        rm -rf "${CONFIGDIR}"
        _vlog "removed ${CONFIGDIR}"
    fi
fi

if ls ${TRACKER_GLOB} >/dev/null 2>&1; then
    echo ""
    echo "Version tracker files found in ~/.cache:"
    ls -1 ${TRACKER_GLOB}
    read -r -p "These may be shared with your own scripts. Delete them? [y/N] " ans
    if [ "$(echo "${ans}" | tr '[:upper:]' '[:lower:]')" = "y" ]; then
        rm -f ${TRACKER_GLOB}
        _vlog "trackers removed"
    fi
fi

echo ""
echo "Removed: ${BINDIR}/upkeep, ${BINDIR}/upkeep-gui, ${LIBDIR}, desktop entry and icons."
echo "Done. AppImage files themselves were NOT touched."
