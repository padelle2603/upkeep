"""The AppImage ships its own copy of the GTK theme.

Pointed at packaging/, the same code path that runs inside the bundle must
find the vendored theme. If it does not, the AppImage opens with whatever
theme the host happens to have, which is what the build guard exists to
prevent: a missing stylesheet is silent, like a missing icon theme.
"""

import os
import pathlib

from upkeep.gui import theme as theme_mod

BUNDLED_THEME = pathlib.Path(__file__).resolve().parents[1] / "packaging" / "themes" / "adw-gtk3"


class TestBundledTheme:
    def test_vendored_theme_is_discoverable(self, monkeypatch):
        packaging = str(BUNDLED_THEME.parents[1])
        monkeypatch.setenv("XDG_DATA_DIRS", packaging)
        monkeypatch.setenv("XDG_DATA_HOME", os.path.join(packaging, "no-such-share"))
        assert theme_mod.theme_available(theme_mod.PREFERRED_THEME) is True

    def test_vendored_theme_has_both_schemes(self):
        assert (BUNDLED_THEME / "gtk-3.0" / "gtk.css").is_file()
        assert (BUNDLED_THEME / "gtk-3.0" / "gtk-dark.css").is_file()

    def test_vendored_theme_ships_its_license(self):
        """LGPL-2.1 requires the license to travel with the files."""
        assert "GNU LESSER GENERAL PUBLIC LICENSE" in (BUNDLED_THEME / "LICENSE").read_text()
        assert (BUNDLED_THEME / "ORIGIN.md").is_file()
