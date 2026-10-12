import pytest

pytest.importorskip("gi")

from upkeep.gui.main_window import check_summary, _plural  # noqa: E402


class TestPlural:
    def test_singular(self):
        assert _plural(1, "app") == "1 app"

    def test_plural(self):
        assert _plural(2, "app") == "2 apps"

    def test_explicit_plural(self):
        assert _plural(2, "update") == "2 updates"

    def test_zero_is_plural(self):
        assert _plural(0, "error") == "0 errors"


class TestCheckSummary:
    def test_all_up_to_date(self):
        assert check_summary(7, 0, 0) == "7 apps  ·  all up to date"

    def test_outdated_replaces_all_up_to_date(self):
        assert check_summary(7, 2, 0) == "7 apps  ·  2 updates available"

    def test_errors_shown(self):
        assert check_summary(7, 0, 1) == "7 apps  ·  1 error"

    def test_outdated_and_errors_together(self):
        result = check_summary(7, 2, 3)
        assert result == "7 apps  ·  2 updates available  ·  3 errors"

    def test_errors_suppress_all_up_to_date(self):
        assert "all up to date" not in check_summary(3, 0, 2)

    def test_singular_app(self):
        assert check_summary(1, 0, 0) == "1 app  ·  all up to date"

    def test_no_apps(self):
        assert check_summary(0, 0, 0) == "no apps to check"