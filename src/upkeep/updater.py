# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import glob
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.error

from pathlib import Path

from . import config
from . import github

USER_AGENT = f"upkeep/{__import__('upkeep').__version__}"

DESKTOP_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "applications"
ICON_STORE_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "upkeep" / "icons"


def sanitize_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "").strip().lower()).strip("-")


def desktop_path(app):
    return DESKTOP_DIR / f"{sanitize_name(app['name'])}.desktop"


def _extract_appimage_icon(app_image, name):
    tmp = tempfile.mkdtemp(prefix="au-icon-")
    try:
        subprocess.run(
            [app_image, "--appimage-extract"],
            cwd=tmp, timeout=120,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        root = os.path.join(tmp, "squashfs-root")
        if not os.path.isdir(root):
            return None
        pngs = []
        svgs = []
        for p in glob.glob(os.path.join(root, "**", "*"), recursive=True):
            if not os.path.isfile(p):
                continue
            low = p.lower()
            if low.endswith(".png"):
                try:
                    pngs.append((os.path.getsize(p), p))
                except OSError:
                    pass
            elif low.endswith(".svg"):
                svgs.append(p)
        if pngs:
            pngs.sort(reverse=True)
            src = pngs[0][1]
            dest = ICON_STORE_DIR / f"{sanitize_name(name)}.png"
            ICON_STORE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            return str(dest)
        if svgs:
            dest = ICON_STORE_DIR / f"{sanitize_name(name)}.svg"
            ICON_STORE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(svgs[0], dest)
            return str(dest)
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return None


def write_desktop_entry(app, settings):
    try:
        create = settings.get("create_desktop", True)
    except AttributeError:
        create = True
    if not create:
        return None
    target = config.app_target_path(app)
    if not os.path.exists(target):
        return None
    display_name = (app["name"].replace("-", " ").replace("_", " ").strip() or app["name"]).title()
    icon = _extract_appimage_icon(target, app["name"])
    if not icon:
        icon = "application-x-executable"
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={display_name}\n"
        f"Comment=AppImage {app['name']} (managed by Upkeep)\n"
        f"Exec=\"{target}\"\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
    )
    try:
        DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
        path = desktop_path(app)
        path.write_text(content)
        return str(path)
    except OSError:
        return None


def remove_desktop_entry(app):
    try:
        p = desktop_path(app)
        if p.exists():
            p.unlink()
    except OSError:
        pass


def latest_info(app, timeout=github.DEFAULT_TIMEOUT):
    release = github.fetch_latest_release(app["repo"], timeout=timeout)
    tag = release.get("tag_name")
    if not tag:
        raise github.GitHubError(f"No version found for {app['repo']}", kind="not_found")
    asset = github.select_asset(
        release.get("assets") or [],
        arch=app.get("arch") or "x86_64",
        asset_filter=app.get("asset_filter") or "",
        preferred_name=app["name"].lower(),
    )
    return {
        "tag": tag,
        "asset_name": (asset or {}).get("name") or "",
        "download_url": (asset or {}).get("browser_download_url") or "",
        "published_at": release.get("published_at") or "",
        "html_url": release.get("html_url") or "",
    }


class UpdateResult:
    def __init__(self, app, state, message="", version=None, info=None):
        self.app = app
        self.state = state
        self.message = message
        self.version = version
        self.info = info

    @property
    def ok(self):
        return self.state == "updated" or self.state == "uptodate"


def check_app(app, settings, timeout=github.DEFAULT_TIMEOUT, progress_cb=None):
    local = config.read_local_version(app, settings)
    try:
        info = latest_info(app, timeout=timeout)
    except github.GitHubError as e:
        return UpdateResult(app, "error", str(e), local)
    if not os.path.exists(config.app_target_path(app)):
        return UpdateResult(app, "missing", "Executable not found", local, info)
    if local and not github.newer_than(local, info["tag"]):
        return UpdateResult(app, "uptodate", "Up to date", local, info)
    return UpdateResult(app, "outdated", "", local, info)


def download(url, dest, progress_cb=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    target_dir = os.path.dirname(dest)
    os.makedirs(target_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".download-", suffix=".part", dir=target_dir)
    os.close(fd)
    total = None
    done = 0
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            with open(tmp, "wb") as fh:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total)
        os.chmod(tmp, 0o755)
        os.replace(tmp, dest)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise github.GitHubError(f"Error during download: {e}", kind="download")


def update_app(app, settings, timeout=github.DEFAULT_TIMEOUT, progress_cb=None, confirm_fn=None):
    local = config.read_local_version(app, settings)
    try:
        info = latest_info(app, timeout=timeout)
    except github.GitHubError as e:
        return UpdateResult(app, "error", str(e), local)
    target = config.app_target_path(app)
    missing = not os.path.exists(target)
    if not missing and local and not github.newer_than(local, info["tag"]):
        write_desktop_entry(app, settings)
        return UpdateResult(app, "uptodate", "Up to date", local, info)
    if not info["download_url"]:
        return UpdateResult(app, "error", "No suitable AppImage file in the release.", local, info)
    if confirm_fn and not confirm_fn(app, info, missing=missing):
        return UpdateResult(app, "skipped", "Update skipped by the user.", local, info)
    try:
        download(info["download_url"], target, progress_cb=progress_cb)
        config.write_local_version(app, settings, info["tag"])
        write_desktop_entry(app, settings)
    except github.GitHubError as e:
        return UpdateResult(app, "error", str(e), local, info)
    return UpdateResult(app, "updated", "Updated to " + info["tag"], info["tag"], info)


def list_apps(config_data):
    return config_data.get("apps") or []


def default_install_dir(settings):
    return config.expand(settings.get("default_install_dir") or config.DEFAULT_SETTINGS["default_install_dir"])
