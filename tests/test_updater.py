import pytest
from upkeep import updater
from upkeep.updater import sanitize_name, write_desktop_entry


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
