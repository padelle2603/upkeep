#!/bin/bash
# Copyright (C) 2026 padelle2603
# SPDX-License-Identifier: GPL-3.0-or-later
set -e

PREFIX="${HOME}/.local"
BINDIR="${PREFIX}/bin"
LIBDIR="${PREFIX}/lib/upkeep"
APPDIR="${PREFIX}/share/applications"
ICONDIR="${PREFIX}/share/icons/hicolor"
CONFIGDIR="${HOME}/.config/upkeep"
TRACKER_GLOB="${HOME}/.cache/appimage_tracker_*.txt"

echo "Uninstalling Upkeep"

rm -f "${BINDIR}/upkeep"
rm -f "${BINDIR}/upkeep-gui"
rm -rf "${LIBDIR}"

rm -f "${APPDIR}/upkeep.desktop"
# Remove the per-app .desktop entries created for managed AppImages
while IFS= read -r f; do
    rm -f "${f}"
    echo "  removed ${f}"
done < <(grep -l "Upkeep" "${APPDIR}"/*.desktop 2>/dev/null || true)

rm -rf "${ICONDIR}/scalable/apps/upkeep.svg"
for size in 48 128 256 512; do
    rm -f "${ICONDIR}/${size}x${size}/apps/upkeep.png"
done

if [ -d "${CONFIGDIR}" ]; then
    echo ""
    read -r -p "Remove the configuration folder ${CONFIGDIR}? [y/N] " ans
    if [ "$(echo "${ans}" | tr '[:upper:]' '[:lower:]')" = "y" ]; then
        rm -rf "${CONFIGDIR}"
        echo "  removed ${CONFIGDIR}"
    else
        echo "  kept ${CONFIGDIR}"
    fi
fi

if ls ${TRACKER_GLOB} >/dev/null 2>&1; then
    echo ""
    echo "Version tracker files were found in ~/.cache:"
    ls -1 ${TRACKER_GLOB}
    read -r -p "These may be shared with your own scripts. Delete them? [y/N] " ans
    if [ "$(echo "${ans}" | tr '[:upper:]' '[:lower:]')" = "y" ]; then
        rm -f ${TRACKER_GLOB}
        echo "  trackers removed"
    else
        echo "  trackers kept"
    fi
fi

echo ""
echo "Done. AppImage files themselves were NOT touched."
