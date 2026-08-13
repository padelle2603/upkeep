# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import json
import re
import urllib.request
import urllib.error

API_BASE = "https://api.github.com/repos/{repo}/releases/latest"
DEFAULT_TIMEOUT = 10
USER_AGENT = f"upkeep/{__import__('upkeep').__version__}"


class GitHubError(Exception):
    def __init__(self, message, kind="error"):
        super().__init__(message)
        self.kind = kind


def _request(url, timeout=DEFAULT_TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise GitHubError(f"Network error for {url}: {e}", kind="network")


def fetch_latest_release(repo, timeout=DEFAULT_TIMEOUT):
    repo = (repo or "").strip().lstrip("@/")
    if "/" not in repo:
        raise GitHubError(f"Invalid repo: {repo!r} (expected 'owner/repo')", kind="invalid")
    status, body = _request(API_BASE.format(repo=repo), timeout=timeout)
    if status == 200:
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise GitHubError(f"Invalid JSON response from GitHub for {repo}", kind="invalid")
    if status == 403:
        msg = "GitHub API rate limit reached. Try again later."
        try:
            data = json.loads(body)
            if "message" in data:
                msg = data["message"]
        except Exception:
            pass
        raise GitHubError(msg, kind="rate_limit")
    if status == 404:
        raise GitHubError(f"Repository '{repo}' not found or has no releases.", kind="not_found")
    raise GitHubError(f"GitHub responded with HTTP {status} for {repo}", kind="http")


def strip_v(version):
    return re.sub(r"^[vV]", "", (version or "").strip())


def _tokens(v):
    return [int(p) if p.isdigit() else p for p in re.split(r"[._\-+]+", strip_v(v))]


def version_compare(a, b):
    if a == b:
        return 0
    ta, tb = _tokens(a), _tokens(b)
    for x, y in zip(ta, tb):
        if type(x) == type(y):
            if x < y:
                return -1
            if x > y:
                return 1
        else:
            sx, sy = str(x), str(y)
            if sx < sy:
                return -1
            if sx > sy:
                return 1
    if len(ta) < len(tb):
        return -1
    if len(ta) > len(tb):
        return 1
    return 0


def newer_than(local, remote):
    return local is not None and remote is not None and version_compare(strip_v(local), strip_v(remote)) < 0


ARCH_TOKENS = {
    "x86_64": ("x86_64", "amd64", "x64"),
    "aarch64": ("aarch64", "arm64", "armv8"),
}
ARM_TOKENS = ("arm", "aarch64", "arm64", "armv7", "armv8", "armhf", "armel")
OTHER_ARCH_TOKENS = ("x86_64", "amd64", "x64", "i386", "i686") + ARM_TOKENS


def _is_appimage(name):
    return name.lower().endswith((".appimage", ".appimage.tar.gz"))


def _arch_score(low, arch):
    if arch == "any":
        return 0
    tokens = ARCH_TOKENS.get(arch, ())
    if any(t in low for t in tokens):
        return 10
    if any(t in low for t in OTHER_ARCH_TOKENS):
        return -10
    return 0


def select_asset(assets, arch="x86_64", asset_filter="", preferred_name=None):
    best = None
    best_score = -1
    for asset in assets or []:
        name = asset.get("name") or ""
        low = name.lower()
        if not _is_appimage(low):
            continue
        if asset_filter and not re.search(asset_filter, name):
            continue
        score = _arch_score(low, arch)
        if score < 0:
            continue
        if preferred_name and preferred_name.lower() in low:
            score += 500
        if score > best_score:
            best = asset
            best_score = score
    return best
