import pytest

pytest.importorskip("gi")

from upkeep.gui.main_window import (  # noqa: E402
    PILL_CLASS,
    STATE_LABEL,
    URGENT_STATUS,
    check_summary,
    updates_available,
    _plural,
)


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

class TestUpdatesAvailable:
    def test_singular(self):
        assert updates_available(1) == "1 update available"

    def test_plural(self):
        assert updates_available(3) == "3 updates available"

    def test_same_wording_as_the_summary(self):
        """The banner and the status line must not drift into two phrases."""
        assert updates_available(2) in check_summary(7, 2, 0)


class TestStateTables:
    def test_every_state_has_a_pill_class(self):
        missing = [s for s in STATE_LABEL if s not in PILL_CLASS]
        assert not missing, f"states with no pill styling: {missing}"

    def test_pill_classes_are_known(self):
        known = {"pill-ok", "pill-warn", "pill-err", "pill-pending", ""}
        unknown = {c for c in PILL_CLASS.values() if c not in known}
        assert not unknown, f"pill classes with no styling in style.css: {unknown}"

    def test_only_actionable_states_are_urgent(self):
        """The row button turns accent only when there is something to do."""
        assert set(URGENT_STATUS) == {"outdated", "missing"}
        for state in URGENT_STATUS:
            assert PILL_CLASS[state] in ("pill-warn", "pill-err")
