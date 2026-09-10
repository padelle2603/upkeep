import pytest
from upkeep.cli import cmd_list, cmd_check, STATE_ICON
from unittest.mock import MagicMock, patch


class TestStateIcon:
    def test_has_states(self):
        assert "outdated" in STATE_ICON
        assert "uptodate" in STATE_ICON
        assert "error" in STATE_ICON
        assert "updated" in STATE_ICON
