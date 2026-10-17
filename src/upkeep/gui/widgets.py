# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

"""Widgets shared by the dialogs.

Both dialogs build the same five shapes: a section heading, a labelled
field, a switch, a browse button and the dialog header. Keeping them here
means a change to how a row looks lands in both at once.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

# Every icon name the GUI asks for. Adwaita is the only icon theme the
# AppImage ships, and an icon Adwaita does not have is not a gap: GTK draws a
# filled box instead, which is how download-symbolic used to reach users.
# tests/test_gui_theme.py checks this list against Adwaita.
ICON_CHECK = "view-refresh-symbolic"
ICON_UPDATE_ALL = "go-down-symbolic"
ICON_ADD = "list-add-symbolic"
ICON_MENU = "open-menu-symbolic"
ICON_CLOSE = "window-close-symbolic"
ICON_BROWSE = "folder-open-symbolic"
ICON_COPY = "edit-copy-symbolic"
ICON_EDIT = "document-edit-symbolic"
ICON_REMOVE = "user-trash-symbolic"
ICON_DOWNLOAD = "document-open-symbolic"
ICON_UPDATE_AVAILABLE = "software-update-available-symbolic"

ALL_ICONS = (
    ICON_CHECK,
    ICON_UPDATE_ALL,
    ICON_ADD,
    ICON_MENU,
    ICON_CLOSE,
    ICON_BROWSE,
    ICON_COPY,
    ICON_EDIT,
    ICON_REMOVE,
    ICON_DOWNLOAD,
    ICON_UPDATE_AVAILABLE,
)


def use_header(dialog, accept_label="Save", cancel_label="Cancel"):
    """Put Cancel and Save in the title bar instead of a strip below.

    GNOME stopped putting dialog buttons in a row at the bottom; the header
    is where they live now, and it leaves the fields room to breathe.
    Gtk.Dialog.set_use_header_bar() would do this, but PyGObject does not
    expose it, so the header is built here and the responses are sent by hand.
    """
    header = Gtk.HeaderBar()
    header.set_show_close_button(False)

    # The header bar of a Gtk.Dialog does not pick the window title up on its
    # own, so it is set here: an unnamed dialog is a dialog nobody can find.
    title = Gtk.Label(label=dialog.get_title())
    title.get_style_context().add_class("header-title")
    header.set_custom_title(title)

    cancel = Gtk.Button(label=cancel_label)
    cancel.get_style_context().add_class("flat")
    cancel.connect("clicked", lambda *_: dialog.response(Gtk.ResponseType.CANCEL))
    header.pack_start(cancel)

    save = Gtk.Button(label=accept_label)
    save.get_style_context().add_class("suggested-action")
    save.connect("clicked", lambda *_: dialog.response(Gtk.ResponseType.ACCEPT))
    header.pack_end(save)

    dialog.set_titlebar(header)
    dialog.set_default_response(Gtk.ResponseType.ACCEPT)
    return header


def section(title):
    lab = Gtk.Label(label=title, xalign=0)
    lab.get_style_context().add_class("section-title")
    lab.set_margin_top(14)
    lab.set_margin_bottom(2)
    return lab


def field(label, widget, label_width=150):
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    lab = Gtk.Label(label=label, xalign=0)
    lab.get_style_context().add_class("field-label")
    lab.set_size_request(label_width, -1)
    lab.set_valign(Gtk.Align.CENTER)
    row.pack_start(lab, False, False, 0)
    row.pack_start(widget, True, True, 0)
    return row


def switch_row(label, active, subtitle=""):
    """A labelled switch, and the switch itself to read back when saving."""
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.set_margin_top(5)
    row.set_margin_bottom(5)

    labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    lab = Gtk.Label(label=label, xalign=0)
    lab.get_style_context().add_class("switch-label")
    labels.pack_start(lab, False, False, 0)
    if subtitle:
        sub = Gtk.Label(label=subtitle, xalign=0)
        sub.get_style_context().add_class("hint-label")
        labels.pack_start(sub, False, False, 0)
    row.pack_start(labels, True, True, 0)

    switch = Gtk.Switch()
    switch.set_valign(Gtk.Align.CENTER)
    switch.set_active(bool(active))
    row.pack_start(switch, False, False, 0)
    return row, switch


def browse_button(callback):
    btn = Gtk.Button.new_from_icon_name(ICON_BROWSE, Gtk.IconSize.BUTTON)
    btn.get_style_context().add_class("flat")
    btn.set_tooltip_text("Browse…")
    btn.connect("clicked", callback)
    return btn


def flat_button(label, callback):
    btn = Gtk.Button(label=label)
    btn.get_style_context().add_class("flat")
    btn.connect("clicked", callback)
    return btn