"""Theme selection and the icons the GUI depends on.

The Adwaita check is the interesting one: the AppImage prunes every icon
theme but Adwaita, and an icon Adwaita lacks is drawn by GTK as a filled
box. That is silent, it happens on the user's screen, and it is not covered
by any smoke test, so it is checked here.
"""

import os

import pytest

from upkeep.gui import theme as theme_mod


class TestThemeDirs:
    def test_includes_user_and_system_roots(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
        monkeypatch.setenv("XDG_DATA_DIRS", "/opt/share:/usr/share")
        dirs = theme_mod.theme_dirs()
        assert str(tmp_path / "share" / "themes") in dirs
        assert "/opt/share/themes" in dirs
        assert "/usr/share/themes" in dirs

    def test_home_defaults_when_env_is_empty(self, monkeypatch):
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
        dirs = theme_mod.theme_dirs()
        assert os.path.expanduser("~/.themes") in dirs
        assert "/usr/share/themes" in dirs


class TestThemeAvailable:
    def _make(self, root, name, stylesheet="gtk.css"):
        path = root / "themes" / name / "gtk-3.0"
        path.mkdir(parents=True)
        (path / stylesheet).write_text("")

    def test_finds_theme_with_light_stylesheet(self, monkeypatch, tmp_path):
        self._make(tmp_path, "adw-gtk3")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("XDG_DATA_DIRS", "/nonexistent")
        assert theme_mod.theme_available("adw-gtk3") is True

    def test_dark_only_theme_counts(self, monkeypatch, tmp_path):
        self._make(tmp_path, "adw-gtk3", stylesheet="gtk-dark.css")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("XDG_DATA_DIRS", "/nonexistent")
        assert theme_mod.theme_available("adw-gtk3") is True

    def test_missing_theme_is_false(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("XDG_DATA_DIRS", "/nonexistent")
        assert theme_mod.theme_available("adw-gtk3") is False
        assert theme_mod.theme_available("no-such-theme-anywhere") is False

    def test_searches_every_xdg_root(self, monkeypatch, tmp_path):
        self._make(tmp_path / "system", "adw-gtk3")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "empty"))
        monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "system"))
        assert theme_mod.theme_available("adw-gtk3") is True


class TestIconsExistInAdwaita:
    @pytest.fixture
    def adwaita_theme(self):
        gi = pytest.importorskip("gi")
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        settings = Gtk.Settings.get_default()
        if settings is None:
            # No display: the GitHub runner has none, and Gtk.Settings is
            # created from the display connection.
            pytest.skip("no display: GTK settings unavailable")
        previous = settings.get_property("gtk-icon-theme-name")
        settings.set_property("gtk-icon-theme-name", "Adwaita")
        icons = Gtk.IconTheme.get_default()
        icons.rescan_if_needed()
        if not icons.has_icon("view-refresh-symbolic"):
            settings.set_property("gtk-icon-theme-name", previous)
            pytest.skip("Adwaita icon theme is not installed")
        yield icons
        settings.set_property("gtk-icon-theme-name", previous)

    def test_every_gui_icon_is_in_the_theme_the_appimage_ships(self, adwaita_theme):
        from upkeep.gui.widgets import ALL_ICONS

        missing = [name for name in ALL_ICONS if not adwaita_theme.has_icon(name)]
        assert not missing, (
            f"icons missing from Adwaita, drawn as a filled box in the AppImage: {missing}"
        )
