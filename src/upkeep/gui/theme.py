# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

"""Which GTK theme the window is painted with.

adw-gtk3 is the GTK3 port of the libadwaita theme: rounded corners, pastel
surfaces, pill buttons. It is plain CSS, so asking for it costs nothing at
runtime. When it is not installed the system theme stays in place, which is
why this never fails: a theme is a preference, not a requirement.

Light and dark are the system's business. Forcing the theme name does not
touch gtk-application-prefer-dark-theme, so a user on prefer-dark keeps
getting the dark variant of whichever theme is in use.
"""

import os

# The GTK3 port of the libadwaita theme. Also known as adw-gtk3-dark, which
# ships the same name with the dark stylesheet; one entry covers both.
PREFERRED_THEME = "adw-gtk3"

_THEME_STYLESHEETS = ("gtk.css", "gtk-dark.css")


def theme_dirs():
    """Where GTK3 looks for themes, in the order it looks.

    Mirrors gtk_get_theme_dir() plus the user's ~/.themes, which is why this
    reads XDG itself instead of asking Gtk: the answer has to be available
    without a display.
    """
    roots = []
    home = os.path.expanduser("~")
    roots.append(os.path.join(home, ".themes"))
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    roots.append(os.path.join(data_home, "themes"))
    roots.append(os.path.join(home, ".local", "share", "flatpak", "exports", "share", "themes"))
    roots.append(os.path.join("/var", "lib", "flatpak", "exports", "share", "themes"))
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    roots.extend(os.path.join(d, "themes") for d in data_dirs.split(":") if d)
    return roots


def theme_available(name=PREFERRED_THEME):
    """True when GTK would find a stylesheet for `name` in the theme path."""
    for root in theme_dirs():
        for stylesheet in _THEME_STYLESHEETS:
            if os.path.isfile(os.path.join(root, name, "gtk-3.0", stylesheet)):
                return True
    return False


def apply_theme():
    """Use the preferred theme when it is installed, otherwise change nothing.

    Returns the theme name in use, so the caller can log or test it.
    """
    import gi

    # Without this, an importer that has not touched Gtk yet gets whichever
    # version girepository picks first — GTK 4 here — and a theme name means
    # something different to each.
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    settings = Gtk.Settings.get_default()
    if settings is None:
        return ""
    current = settings.get_property("gtk-theme-name")
    if current == PREFERRED_THEME or not theme_available():
        return current
    settings.set_property("gtk-theme-name", PREFERRED_THEME)
    return PREFERRED_THEME