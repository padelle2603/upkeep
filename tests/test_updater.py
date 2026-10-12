import pytest
from unittest.mock import patch
from upkeep import updater
from upkeep.github import GitHubError
from upkeep.updater import sanitize_name, write_desktop_entry


class TestErrorKind:
    """A rate limit is not a broken repo, and the CLI stops on the first one.

    If the kind is lost on the way out of check_app, cmd_check cannot tell them
    apart: it would keep spending requests that are already doomed.
    """

    def _check(self, kind):
        app = {"name": "X", "repo": "o/r"}
        with patch.object(updater, "latest_info", side_effect=GitHubError("m", kind=kind)):
            with patch.object(updater.config, "read_local_version", return_value="1.0"):
                return updater.check_app(app, {})

    def test_rate_limit_is_labelled(self):
        assert self._check("rate_limit").kind == "rate_limit"

    def test_not_found_is_labelled(self):
        assert self._check("not_found").kind == "not_found"

    def test_network_is_labelled(self):
        assert self._check("network").kind == "network"

    def test_successful_check_has_no_kind(self):
        app = {"name": "X", "repo": "o/r"}
        info = {"tag": "v2.0", "asset_name": "", "download_url": "", "published_at": "", "html_url": ""}
        with patch.object(updater, "latest_info", return_value=info):
            with patch.object(updater.config, "read_local_version", return_value="1.0"):
                with patch.object(updater.config, "app_target_path", return_value="/nonexistent"):
                    result = updater.check_app(app, {})
        assert result.state == "missing"
        assert result.kind == ""

    def test_update_app_propagates_the_kind(self):
        app = {"name": "X", "repo": "o/r"}
        with patch.object(updater, "latest_info", side_effect=GitHubError("m", kind="rate_limit")):
            with patch.object(updater.config, "read_local_version", return_value="1.0"):
                result = updater.update_app(app, {})
        assert result.state == "error"
        assert result.kind == "rate_limit"


class TestSanitizeName:
    def test_normal_name(self):
        assert sanitize_name("MyApp") == "myapp"

    def test_special_chars(self):
        assert sanitize_name("My App!") == "my-app"

    def test_empty(self):
        assert sanitize_name("") == ""

    def test_none(self):
        assert sanitize_name(None) == ""

    def test_leading_trailing(self):
        assert sanitize_name("  MyApp  ") == "myapp"

    def test_preserves_dots(self):
        assert sanitize_name("my.app") == "my.app"

    def test_preserves_hyphens(self):
        assert sanitize_name("my-app") == "my-app"

    def test_preserves_underscores(self):
        assert sanitize_name("my_app") == "my_app"


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """Point the CLI-command helpers at a tmp dir, never at the real home."""
    bin_dir = tmp_path / "bin"
    monkeypatch.setattr(updater, "LOCAL_BIN", bin_dir)
    monkeypatch.setenv("PATH", str(bin_dir))
    source = tmp_path / "Upkeep.AppImage"
    source.write_bytes(b"\x7fELF" + b"\x00" * 5 + b"AI\x02")
    monkeypatch.setenv("APPIMAGE", str(source))
    return bin_dir, source


class TestRunningAppimage:
    def test_reads_the_env_var(self, cli_env):
        _, source = cli_env
        assert updater.running_appimage() == str(source)

    def test_absent_outside_an_appimage(self, monkeypatch):
        monkeypatch.delenv("APPIMAGE", raising=False)
        assert updater.running_appimage() is None

    def test_never_falls_back_to_appdir(self, monkeypatch):
        """$APPDIR is the mount that dies with the process."""
        monkeypatch.delenv("APPIMAGE", raising=False)
        monkeypatch.setenv("APPDIR", "/tmp/.mount_UpkeepXXXX")
        assert updater.running_appimage() is None


class TestCliCommand:
    def test_creates_a_symlink(self, cli_env):
        bin_dir, source = cli_env
        ok, message = updater.set_cli_command(True)
        link = bin_dir / "upkeep"
        assert ok, message
        assert link.is_symlink()
        assert link.resolve() == source.resolve()

    def test_creates_the_folder_if_missing(self, cli_env):
        bin_dir, _ = cli_env
        assert not bin_dir.exists()
        updater.set_cli_command(True)
        assert bin_dir.is_dir()

    def test_active_reflects_the_filesystem(self, cli_env):
        bin_dir, _ = cli_env
        assert updater.cli_command_active() is False
        updater.set_cli_command(True)
        assert updater.cli_command_active() is True

    def test_removing_is_idempotent(self, cli_env):
        bin_dir, _ = cli_env
        updater.set_cli_command(True)
        ok, _ = updater.set_cli_command(False)
        assert ok
        assert not (bin_dir / "upkeep").exists()
        ok, _ = updater.set_cli_command(False)
        assert ok

    def test_toggling_twice_lands_on_the_same_link(self, cli_env):
        bin_dir, source = cli_env
        updater.set_cli_command(True)
        first = (bin_dir / "upkeep").readlink()
        updater.set_cli_command(False)
        updater.set_cli_command(True)
        assert (bin_dir / "upkeep").readlink() == first == source

    def test_real_file_is_never_clobbered(self, cli_env):
        bin_dir, _ = cli_env
        bin_dir.mkdir(parents=True)
        victim = bin_dir / "upkeep"
        victim.write_text("#!/bin/sh\necho not upkeep\n")
        victim.chmod(0o755)
        ok, message = updater.set_cli_command(True)
        assert ok is False
        assert "not a symlink" in message
        assert victim.read_text().endswith("echo not upkeep\n")
        assert not victim.is_symlink()

    def test_stale_link_is_repointed(self, cli_env):
        bin_dir, source = cli_env
        bin_dir.mkdir(parents=True)
        link = bin_dir / "upkeep"
        gone = bin_dir / "elsewhere.AppImage"
        gone.write_bytes(b"")
        link.symlink_to(gone)
        gone.unlink()
        ok, message = updater.set_cli_command(True)
        assert ok, message
        assert link.resolve() == source.resolve()

    def test_outside_an_appimage_it_declines(self, cli_env, monkeypatch):
        bin_dir, _ = cli_env
        monkeypatch.delenv("APPIMAGE", raising=False)
        ok, message = updater.set_cli_command(True)
        assert ok is False
        assert "AppImage" in message
        assert not (bin_dir / "upkeep").exists()


class TestPathWarning:
    def test_quiet_when_bin_is_in_path(self, cli_env):
        assert updater.path_warning() == ""

    def test_explains_when_it_is_not(self, cli_env, monkeypatch):
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        warning = updater.path_warning()
        assert str(cli_env[0]) in warning
        assert "export PATH=" in warning
        assert "hash -r" in warning


@pytest.fixture
def desktop_env(tmp_path, monkeypatch):
    """Isolate write_desktop_entry from the real home and from AppImage extraction."""
    app = {"name": "Cheat Engine"}
    exe = tmp_path / "Cheat Engine.AppImage"
    exe.write_text("")
    monkeypatch.setattr(updater, "DESKTOP_DIR", tmp_path / "applications")
    monkeypatch.setattr(updater.config, "app_target_path", lambda a: str(exe))
    monkeypatch.setattr(updater, "_extract_appimage_icon", lambda image, name: "/icons/x.png")
    monkeypatch.setattr(updater, "_refresh_desktop_database", lambda: None)
    return app, exe


class TestWriteDesktopEntry:
    def test_exec_uses_double_quotes(self, desktop_env):
        app, exe = desktop_env
        write_desktop_entry(app, {})
        content = (updater.DESKTOP_DIR / "cheat-engine.desktop").read_text()
        assert f'Exec="{exe}"' in content
        assert "'" not in content

    def test_try_exec_present(self, desktop_env):
        """Without it the launcher keeps showing an entry that opens nothing."""
        app, exe = desktop_env
        write_desktop_entry(app, {})
        content = (updater.DESKTOP_DIR / "cheat-engine.desktop").read_text()
        assert f'TryExec="{exe}"' in content

    def test_try_exec_comes_after_exec(self, desktop_env):
        """desktop-file-utils requires Exec before TryExec."""
        app, _ = desktop_env
        write_desktop_entry(app, {})
        content = (updater.DESKTOP_DIR / "cheat-engine.desktop").read_text()
        assert content.index("\nExec=") < content.index("\nTryExec=")

    def test_version_key_present(self, desktop_env):
        app, _ = desktop_env
        write_desktop_entry(app, {})
        content = (updater.DESKTOP_DIR / "cheat-engine.desktop").read_text()
        assert "Version=1.0" in content

    def test_desktop_group_is_first(self, desktop_env):
        app, _ = desktop_env
        write_desktop_entry(app, {})
        content = (updater.DESKTOP_DIR / "cheat-engine.desktop").read_text()
        assert content.startswith("[Desktop Entry]\n")

    def test_returns_path(self, desktop_env):
        app, _ = desktop_env
        result = write_desktop_entry(app, {})
        assert result == str(updater.DESKTOP_DIR / "cheat-engine.desktop")

    def test_respects_create_desktop_false(self, desktop_env):
        app, _ = desktop_env
        assert write_desktop_entry(app, {"create_desktop": False}) is None
        assert not (updater.DESKTOP_DIR / "cheat-engine.desktop").exists()

    def test_respects_per_app_opt_out(self, desktop_env):
        app, _ = desktop_env
        assert write_desktop_entry({**app, "create_desktop": False}, {}) is None
        assert not (updater.DESKTOP_DIR / "cheat-engine.desktop").exists()

    def test_global_false_wins_over_per_app_true(self, desktop_env):
        app, _ = desktop_env
        result = write_desktop_entry({**app, "create_desktop": True}, {"create_desktop": False})
        assert result is None
        assert not (updater.DESKTOP_DIR / "cheat-engine.desktop").exists()

    def test_per_app_true_creates_entry(self, desktop_env):
        app, _ = desktop_env
        result = write_desktop_entry({**app, "create_desktop": True}, {})
        assert result == str(updater.DESKTOP_DIR / "cheat-engine.desktop")

    def test_skips_missing_executable(self, desktop_env):
        app, exe = desktop_env
        exe.unlink()
        assert write_desktop_entry(app, {}) is None
        assert not (updater.DESKTOP_DIR / "cheat-engine.desktop").exists()

    def test_falls_back_to_generic_icon(self, desktop_env, monkeypatch):
        app, _ = desktop_env
        monkeypatch.setattr(updater, "_extract_appimage_icon", lambda image, name: None)
        write_desktop_entry(app, {})
        content = (updater.DESKTOP_DIR / "cheat-engine.desktop").read_text()
        assert "Icon=application-x-executable" in content
