# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "upkeep"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_SETTINGS = {
    "default_install_dir": "~/.local/share/applications/Appimages",
    "tracker_dir": "~/.cache",
    "default_arch": "x86_64",
    "check_on_startup": True,
    "confirm_download": True,
    "create_desktop": True,
}

DEFAULT_ARCH = "x86_64"
ARCHS = ("x86_64", "aarch64", "any")


def expand(path):
    if path is None or path == "":
        return None
    return str(Path(path).expanduser())


def normalize_app(app):
    d = dict(app)
    d["name"] = (d.get("name") or "").strip()
    d["repo"] = (d.get("repo") or "").strip().lstrip("@/")
    d["install_dir"] = expand(d.get("install_dir") or None)
    d["custom_path"] = expand(d.get("custom_path") or None)
    d["asset_filter"] = (d.get("asset_filter") or "").strip()
    d["arch"] = d.get("arch") or DEFAULT_ARCH
    if d["arch"] not in ARCHS:
        d["arch"] = DEFAULT_ARCH
    d["auto_update"] = bool(d.get("auto_update", False))
    d["enabled"] = bool(d.get("enabled", True))
    return d


def load_config():
    config = {"settings": dict(DEFAULT_SETTINGS), "apps": []}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            settings = data.get("settings") or {}
            config["settings"] = {**DEFAULT_SETTINGS, **settings}
            config["apps"] = [normalize_app(a) for a in data.get("apps") or []]
        except (json.JSONDecodeError, OSError):
            config = {"settings": dict(DEFAULT_SETTINGS), "apps": []}
    return config


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")


def get_tracker_file(app, settings):
    tracker_dir = expand(settings.get("tracker_dir") or "~/.cache")
    return Path(tracker_dir) / f"appimage_tracker_{app['name']}.txt"


def read_local_version(app, settings):
    tracker = get_tracker_file(app, settings)
    if tracker.exists():
        return tracker.read_text().strip()
    return None


def write_local_version(app, settings, version):
    tracker = get_tracker_file(app, settings)
    tracker.parent.mkdir(parents=True, exist_ok=True)
    tracker.write_text(version + "\n")


def app_target_path(app):
    if app.get("custom_path"):
        return app["custom_path"]
    base = app.get("install_dir") or expand(DEFAULT_SETTINGS["default_install_dir"])
    return os.path.join(base, app["name"] + ".AppImage")


def app_target_dir(app):
    return os.path.dirname(app_target_path(app))
