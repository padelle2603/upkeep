import inspect
import re

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from upkeep.gui import main_window as mw  # noqa: E402


class TestLoadCss:
    def test_uses_only_api_that_exists(self):
        """GTK3 has no add_provider_for_display; calling it crashes do_startup."""
        source = inspect.getsource(mw._load_css)
        called = set(re.findall(r"Gtk\.StyleContext\.(\w+)", source))
        assert called, "_load_css should register the css provider"
        missing = [name for name in called if not hasattr(Gtk.StyleContext, name)]
        assert not missing, f"StyleContext API not available in GTK3: {missing}"

    def test_provider_registration_is_not_left_unguarded(self):
        """A failure here must not take the whole window down."""
        source = inspect.getsource(mw._load_css)
        assert source.count("try:") == 1, "expected a single guard block"
        guard_body = source.split("try:", 1)[1]
        assert "add_provider_for" in guard_body, (
            "provider registration must sit inside the try block, "
            "otherwise do_startup raises and the GUI never opens"
        )