import pytest
from upkeep.config import (
    DEFAULT_SETTINGS,
    DEFAULT_ARCH,
    ARCHS,
    expand,
    normalize_app,
    load_config,
    save_config,
)


class TestDefaultSettings:
    def test_has_required_keys(self):
        assert "default_install_dir" in DEFAULT_SETTINGS
        assert "check_on_startup" in DEFAULT_SETTINGS
        assert "confirm_download" in DEFAULT_SETTINGS

    def test_archs(self):
        assert "x86_64" in ARCHS
        assert "aarch64" in ARCHS
        assert "any" in ARCHS


class TestExpand:
    def test_expand_none(self):
        assert expand(None) is None

    def test_expand_empty(self):
        assert expand("") is None

    def test_expand_path(self):
        result = expand("~/test")
        assert result is not None
        assert "test" in result


class TestNormalizeApp:
    def test_basic_normalize(self):
        app = {"name": "TestApp", "repo": "owner/repo"}
        result = normalize_app(app)
        assert result["name"] == "TestApp"
        assert result["repo"] == "owner/repo"
        assert result["arch"] == DEFAULT_ARCH

    def test_invalid_arch_falls_back(self):
        app = {"name": "Test", "repo": "a/b", "arch": "invalid"}
        result = normalize_app(app)
        assert result["arch"] == DEFAULT_ARCH

    def test_strips_prefix(self):
        app = {"name": "App", "repo": "@/owner/repo"}
        result = normalize_app(app)
        assert result["repo"] == "owner/repo"

    def test_auto_update_default(self):
        app = {"name": "App", "repo": "a/b"}
        result = normalize_app(app)
        assert result["auto_update"] is False

    def test_enabled_default(self):
        app = {"name": "App", "repo": "a/b"}
        result = normalize_app(app)
        assert result["enabled"] is True


class TestConfigRoundtrip:
    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("upkeep.config.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("upkeep.config.CONFIG_FILE", tmp_path / "config.json")
        cfg = {"settings": dict(DEFAULT_SETTINGS), "apps": [{"name": "X", "repo": "a/b"}]}
        save_config(cfg)
        loaded = load_config()
        assert loaded["apps"][0]["name"] == "X"

    def test_load_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("upkeep.config.CONFIG_DIR", tmp_path)
        monkeypatch.setattr("upkeep.config.CONFIG_FILE", tmp_path / "nonexistent.json")
        loaded = load_config()
        assert loaded["apps"] == []
        assert loaded["settings"] == DEFAULT_SETTINGS

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("upkeep.config.CONFIG_DIR", tmp_path)
        config_file = tmp_path / "config.json"
        config_file.write_text("not json{{{")
        monkeypatch.setattr("upkeep.config.CONFIG_FILE", config_file)
        loaded = load_config()
        assert loaded["apps"] == []
