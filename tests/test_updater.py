# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from upkeep import github, updater, config

SAMPLE_RELEASE = {
    "tag_name": "v1.4.7",
    "html_url": "https://github.com/foo/bar/releases/tag/v1.4.7",
    "published_at": "2026-01-01T00:00:00Z",
    "assets": [
        {"name": "bar-1.4.7-x86_64.AppImage", "browser_download_url": "https://x/bar-x86.AppImage"},
        {"name": "bar-1.4.7-aarch64.AppImage", "browser_download_url": "https://x/bar-arm.AppImage"},
        {"name": "bar-1.4.7.tar.gz", "browser_download_url": "https://x/bar.tar.gz"},
        {"name": "bar-1.4.7-x86_64.AppImage.sig", "browser_download_url": "https://x/bar.sig"},
    ],
}


class FakeResponse:
    def __init__(self, status, data):
        self.status = status
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.data


class TestVersion(unittest.TestCase):
    def test_strip_v(self):
        self.assertEqual(github.strip_v("v1.2.3"), "1.2.3")
        self.assertEqual(github.strip_v("V2.0"), "2.0")
        self.assertEqual(github.strip_v("1.2.3"), "1.2.3")

    def test_compare(self):
        self.assertLess(github.version_compare("1.2.3", "1.2.4"), 0)
        self.assertEqual(github.version_compare("v1.2.3", "1.2.3"), 0)
        self.assertGreater(github.version_compare("1.10.0", "1.9.9"), 0)
        self.assertLess(github.version_compare("0.3.3", "1.0.0"), 0)

    def test_newer_than(self):
        self.assertTrue(github.newer_than("1.0", "1.1"))
        self.assertFalse(github.newer_than("1.1", "1.1"))
        self.assertFalse(github.newer_than(None, "1.1"))


class TestAssetSelection(unittest.TestCase):
    def setUp(self):
        self.assets = SAMPLE_RELEASE["assets"]

    def test_x86_64(self):
        a = github.select_asset(self.assets, arch="x86_64")
        self.assertIn("x86_64", a["name"])

    def test_aarch64(self):
        a = github.select_asset(self.assets, arch="aarch64")
        self.assertEqual(a["name"], "bar-1.4.7-aarch64.AppImage")

    def test_any(self):
        a = github.select_asset(self.assets, arch="any")
        self.assertTrue(a["name"].endswith(".AppImage"))

    def test_filter(self):
        a = github.select_asset(self.assets, arch="any", asset_filter=r"^bar-\d+\.\d+\.\d+-x86_64\.AppImage$")
        self.assertIn("x86_64", a["name"])

    def test_no_asset(self):
        a = github.select_asset([{"name": "only.tar.gz", "browser_download_url": "x"}], arch="x86_64")
        self.assertIsNone(a)


class TestFetch(unittest.TestCase):
    @mock.patch("upkeep.github._request")
    def test_fetch_ok(self, req):
        req.return_value = (200, json.dumps(SAMPLE_RELEASE).encode())
        r = github.fetch_latest_release("foo/bar")
        self.assertEqual(r["tag_name"], "v1.4.7")

    @mock.patch("upkeep.github._request")
    def test_fetch_404(self, req):
        req.return_value = (404, b"{}")
        with self.assertRaises(github.GitHubError) as ctx:
            github.fetch_latest_release("foo/bar")
        self.assertEqual(ctx.exception.kind, "not_found")

    @mock.patch("upkeep.github._request")
    def test_fetch_rate_limit(self, req):
        req.return_value = (403, json.dumps({"message": "API rate limit exceeded"}).encode())
        with self.assertRaises(github.GitHubError) as ctx:
            github.fetch_latest_release("foo/bar")
        self.assertEqual(ctx.exception.kind, "rate_limit")


class TestUpdater(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.settings = {"default_install_dir": self.tmp, "tracker_dir": self.tmp, "create_desktop": True}
        self.app = config.normalize_app({"name": "bar", "repo": "foo/bar", "arch": "x86_64", "install_dir": self.tmp})
        os.makedirs(self.tmp, exist_ok=True)
        self.desktop_patch = mock.patch("upkeep.updater.DESKTOP_DIR", Path(self.tmp) / "applications")
        self.desktop_patch.start()
        self.icon_patch = mock.patch("upkeep.updater._extract_appimage_icon", return_value=None)
        self.icon_patch.start()
        self.target = config.app_target_path(self.app)

    def tearDown(self):
        self.desktop_patch.stop()
        self.icon_patch.stop()

    def _create_file(self):
        with open(self.target, "wb") as f:
            f.write(b"FAKE")
        os.chmod(self.target, 0o755)

    @mock.patch("upkeep.github.fetch_latest_release")
    def test_check_outdated(self, fetch):
        fetch.return_value = SAMPLE_RELEASE
        self._create_file()
        config.write_local_version(self.app, self.settings, "v1.0.0")
        r = updater.check_app(self.app, self.settings)
        self.assertEqual(r.state, "outdated")
        self.assertEqual(r.info["tag"], "v1.4.7")

    @mock.patch("upkeep.github.fetch_latest_release")
    def test_check_uptodate(self, fetch):
        fetch.return_value = SAMPLE_RELEASE
        self._create_file()
        config.write_local_version(self.app, self.settings, "v1.4.7")
        r = updater.check_app(self.app, self.settings)
        self.assertEqual(r.state, "uptodate")

    @mock.patch("upkeep.github.fetch_latest_release")
    def test_check_missing_file(self, fetch):
        fetch.return_value = SAMPLE_RELEASE
        config.write_local_version(self.app, self.settings, "v1.4.7")
        r = updater.check_app(self.app, self.settings)
        self.assertEqual(r.state, "missing")
        self.assertEqual(r.info["tag"], "v1.4.7")

    @mock.patch("upkeep.github.fetch_latest_release")
    @mock.patch("upkeep.updater.download")
    def test_update_app(self, dl, fetch):
        fetch.return_value = SAMPLE_RELEASE
        self._create_file()
        config.write_local_version(self.app, self.settings, "v1.0.0")
        r = updater.update_app(self.app, self.settings)
        self.assertEqual(r.state, "updated")
        self.assertEqual(r.version, "v1.4.7")
        self.assertEqual(dl.call_args[0][1], self.target)
        self.assertEqual(config.read_local_version(self.app, self.settings), "v1.4.7")

    @mock.patch("upkeep.github.fetch_latest_release")
    @mock.patch("upkeep.updater.download")
    def test_update_missing_file_reinstalls(self, dl, fetch):
        fetch.return_value = SAMPLE_RELEASE
        config.write_local_version(self.app, self.settings, "v1.4.7")
        self.assertFalse(os.path.exists(self.target))
        r = updater.update_app(self.app, self.settings)
        self.assertEqual(r.state, "updated")
        self.assertEqual(dl.call_count, 1)

    @mock.patch("upkeep.github.fetch_latest_release")
    @mock.patch("upkeep.updater.download")
    def test_desktop_created_on_update(self, dl, fetch):
        fetch.return_value = SAMPLE_RELEASE
        self._create_file()
        config.write_local_version(self.app, self.settings, "v1.0.0")
        updater.update_app(self.app, self.settings)
        desk = updater.desktop_path(self.app)
        self.assertTrue(desk.exists())
        content = desk.read_text()
        self.assertIn("Name=Bar", content)
        self.assertIn('Exec="%s"' % self.target, content)
        self.assertIn("Icon=application-x-executable", content)
        self.assertIn("Categories=Utility;", content)

    @mock.patch("upkeep.github.fetch_latest_release")
    @mock.patch("upkeep.updater.download")
    def test_desktop_skipped_when_disabled(self, dl, fetch):
        fetch.return_value = SAMPLE_RELEASE
        self.settings["create_desktop"] = False
        self._create_file()
        config.write_local_version(self.app, self.settings, "v1.0.0")
        updater.update_app(self.app, self.settings)
        self.assertFalse(updater.desktop_path(self.app).exists())


if __name__ == "__main__":
    unittest.main()