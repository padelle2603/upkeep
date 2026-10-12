import pytest
from upkeep import config
from upkeep.cli import build_parser, cmd_add, cmd_list, cmd_check, STATE_ICON
from unittest.mock import MagicMock, patch


class TestStateIcon:
    def test_has_states(self):
        assert "outdated" in STATE_ICON
        assert "uptodate" in STATE_ICON
        assert "error" in STATE_ICON
        assert "updated" in STATE_ICON


@pytest.fixture
def cfg_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    return {"settings": dict(config.DEFAULT_SETTINGS), "apps": []}


class TestCmdAddDesktopFlag:
    def test_desktop_entry_enabled_by_default(self, cfg_file):
        args = build_parser().parse_args(["add", "--name", "Waywallen", "--repo", "owner/repo"])
        assert cmd_add(cfg_file, args) == 0
        assert cfg_file["apps"][0]["create_desktop"] is True

    def test_no_desktop_flag_opts_out(self, cfg_file):
        args = build_parser().parse_args(
            ["add", "--name", "Waywallen", "--repo", "owner/repo", "--no-desktop"]
        )
        assert cmd_add(cfg_file, args) == 0
        assert cfg_file["apps"][0]["create_desktop"] is False

    def test_no_desktop_is_persisted(self, cfg_file, tmp_path):
        args = build_parser().parse_args(
            ["add", "--name", "Waywallen", "--repo", "owner/repo", "--no-desktop"]
        )
        cmd_add(cfg_file, args)
        assert config.load_config()["apps"][0]["create_desktop"] is False