# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import os
import subprocess
import threading
import time
from pathlib import Path
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from .. import config
from .. import selfupdate
from .. import updater
from .. import __version__

from . import theme
from .app_dialog import AppDialog
from .settings_dialog import SettingsDialog
from .widgets import (
    ICON_ADD,
    ICON_CHECK,
    ICON_CLOSE,
    ICON_DOWNLOAD,
    ICON_MENU,
    ICON_UPDATE_ALL,
    ICON_UPDATE_AVAILABLE,
)

APP_ID = "io.github.padelle2603.upkeep"
ICON_NAME = "upkeep"
ROW_HINT = "Double-click to edit  ·  right-click for more actions"


def _project_root():
    """Where icons/ and docs/ live.

    Inside the AppImage the package sits at usr/bin/_internal/upkeep/gui, so
    parents[3] lands in the middle of the bundle and finds nothing. AppRun
    exports $APPDIR pointing at the mount point; the icon is at its root.
    """
    appdir = os.environ.get("APPDIR")
    if appdir:
        return Path(appdir)
    return Path(__file__).resolve().parents[3]


def _load_css():
    css = Path(__file__).parent / "style.css"
    if not css.exists():
        return False
    provider = Gtk.CssProvider()
    try:
        provider.load_from_path(str(css))
        # Guarded: an unknown StyleContext API here would take do_startup
        # down with it and the window would never open.
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    except Exception:
        return False
    return True


def get_app_pixbuf(size=64):
    theme_obj = Gtk.IconTheme.get_default()
    try:
        info = theme_obj.lookup_icon(ICON_NAME, size, Gtk.IconLookupFlags.USE_BUILTIN)
        if info is not None:
            return info.load_icon()
    except Exception:
        pass
    svg = _project_root() / "icons" / f"{ICON_NAME}.svg"
    if not svg.exists():
        # Also shipped at the AppImage root as a rendered bitmap.
        svg = _project_root() / "upkeep.svg"
    if svg.exists():
        try:
            from gi.repository import GdkPixbuf
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(svg), size, size, True)
        except Exception:
            pass
    return None


def _icon_available():
    try:
        return Gtk.IconTheme.get_default().has_icon(ICON_NAME)
    except Exception:
        return False


STATE_LABEL = {
    "outdated": "Update available",
    "uptodate": "Up to date",
    "error": "Error",
    "updated": "Up to date",
    "skipped": "Skipped",
    "pending": "Checking…",
    "missing": "Missing file",
}
PILL_CLASS = {
    "outdated": "pill-warn",
    "uptodate": "pill-ok",
    "updated": "pill-ok",
    "error": "pill-err",
    "missing": "pill-err",
    "skipped": "",
    "pending": "pill-pending",
}
# A status worth acting on is the only one that gets the accent colour on its
# row button: six identical primary buttons down the list say nothing.
URGENT_STATUS = ("outdated", "missing")


def _btn_with_icon(label, icon, classes=()):
    btn = Gtk.Button(label=label)
    if icon:
        img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
        btn.set_image(img)
        btn.set_always_show_image(True)
    for c in classes:
        btn.get_style_context().add_class(c)
    return btn


def _flat_btn(label, icon):
    return _btn_with_icon(label, icon, ("flat",))


def _icon_btn(icon, tooltip, classes=()):
    btn = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
    btn.set_tooltip_text(tooltip)
    for c in classes:
        btn.get_style_context().add_class(c)
    return btn


def _reveal(widget):
    """Show a widget that opted out of show_all(), children included.

    show_all() on a no_show_all widget does nothing at all: GTK checks the
    widget's own flag first and returns, so its children stay invisible and
    the banner renders as an empty strip. Walking them here is the fix.
    A ProgressBar has no children at all: its trough is drawn by GTK, and
    asking it for one is an AttributeError, not an empty list.
    """
    widget.show()
    get_children = getattr(widget, "get_children", None)
    if get_children is None:
        return
    for child in get_children():
        child.show_all()


def _plural(n, singular, plural=None):
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def updates_available(count):
    """One wording for 'there is something to update': banner and status line."""
    return f"{_plural(count, 'update')} available"


def check_summary(total, outdated, errors):
    """Human-readable outcome of a check, shown in the status line so the user always sees a result."""
    if not total:
        return "no apps to check"
    parts = [_plural(total, "app")]
    if outdated:
        parts.append(updates_available(outdated))
    elif not errors:
        parts.append("all up to date")
    if errors:
        parts.append(_plural(errors, "error"))
    return "  ·  ".join(parts)


def _describe_exception(exc):
    return f"{type(exc).__name__}: {exc}"


def _copy_to_clipboard(text):
    """Feedback lives in the status line, so copying the path says so too."""
    Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
    return text


class AppRow(Gtk.ListBoxRow):
    def __init__(self, app, settings, on_update, on_edit, on_delete):
        super().__init__()
        self.app = app
        self.status = "unknown"
        self.message = ""
        self.local_version = ""
        self.remote_tag = None
        self.installed = False
        self.path = ""
        self.get_style_context().add_class("app-row")
        self.set_tooltip_text(ROW_HINT)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(9)
        box.set_margin_bottom(9)
        box.set_margin_start(12)
        box.set_margin_end(10)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        info.set_hexpand(True)

        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.name_label = Gtk.Label(label=app["name"], xalign=0)
        self.name_label.get_style_context().add_class("app-name")
        name_row.pack_start(self.name_label, False, False, 0)
        repo_label = Gtk.Label(label=app["repo"], xalign=0)
        repo_label.get_style_context().add_class("app-repo")
        repo_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_row.pack_start(repo_label, False, False, 0)
        info.pack_start(name_row, False, False, 0)

        self.sub_label = Gtk.Label(label="", xalign=0)
        self.sub_label.get_style_context().add_class("app-sub")
        self.sub_label.set_ellipsize(Pango.EllipsizeMode.END)
        info.pack_start(self.sub_label, False, False, 0)

        box.pack_start(info, True, True, 0)

        self.status_label = Gtk.Label(label="")
        self.status_label.get_style_context().add_class("status-pill")
        self.status_label.set_margin_start(8)
        box.pack_start(self.status_label, False, False, 0)

        self.update_btn = _icon_btn(ICON_CHECK, "Update", ("row-action",))
        self.update_btn.connect("clicked", lambda *_: on_update(self))
        box.pack_start(self.update_btn, False, False, 0)

        self.add(box)
        self._build_menu(on_update, on_edit, on_delete)
        self.refresh(settings)

    def _build_menu(self, on_update, on_edit, on_delete):
        """Everything that is not worth a permanent button still has to be reachable."""
        menu = Gtk.Menu()
        self.menu_update_item = Gtk.MenuItem(label="Update")
        self.menu_update_item.connect("activate", lambda *_: on_update(self))
        menu.append(self.menu_update_item)
        edit_item = Gtk.MenuItem(label="Edit…")
        edit_item.connect("activate", lambda *_: on_edit(self))
        menu.append(edit_item)
        copy_item = Gtk.MenuItem(label="Copy install path")
        copy_item.connect("activate", lambda *_: _copy_to_clipboard(self.path))
        menu.append(copy_item)
        menu.append(Gtk.SeparatorMenuItem())
        remove_item = Gtk.MenuItem(label="Remove…")
        remove_item.get_style_context().add_class("destructive-action")
        remove_item.connect("activate", lambda *_: on_delete(self))
        menu.append(remove_item)
        menu.show_all()
        self.menu = menu

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._on_button_press)

    def _on_button_press(self, _widget, event):
        if event.button == 3:
            self.menu.popup_at_pointer(event)
            return True
        return False

    def refresh(self, settings):
        local = config.read_local_version(self.app, settings) or "not installed"
        self.local_version = local
        self.path = config.app_target_path(self.app)
        self.installed = os.path.exists(self.path)
        enabled = self.app.get("enabled", True)
        self.update_btn.set_sensitive(enabled)
        if not self.installed and self.status in ("unknown", "uptodate", "outdated"):
            self.status = "missing"
        self._apply_status()
        self._update_sub()

    def set_status(self, status, info=None, message=""):
        self.status = status
        self.message = message or ""
        if info and info.get("tag"):
            self.remote_tag = info["tag"]
        self._apply_status()
        self._update_sub()

    def _update_sub(self):
        local = self.local_version if self.installed else "not installed"
        if self.remote_tag and self.remote_tag != self.local_version:
            self.sub_label.set_text(f"{local}  →  {self.remote_tag}")
        else:
            self.sub_label.set_text(local)

    def _apply_status(self):
        ctx = self.get_style_context()
        enabled = self.app.get("enabled", True)
        if not enabled:
            ctx.add_class("disabled")
            self.update_btn.set_sensitive(False)
            self.menu_update_item.set_sensitive(False)
            self._set_pill("Disabled", "pill-disabled")
            self._set_urgency(False)
            self._set_reason("")
            return
        ctx.remove_class("disabled")
        self.update_btn.set_sensitive(True)
        self.menu_update_item.set_sensitive(True)
        self._set_pill(STATE_LABEL.get(self.status, ""), PILL_CLASS.get(self.status, ""))
        self._set_urgency(self.status in URGENT_STATUS)
        self._set_reason(self.message if self.status in ("error", "missing") else "")

    def _set_reason(self, text):
        """Surface the reason (rate limit, missing file, ...) without breaking the layout."""
        self.status_label.set_tooltip_text(text)
        self.name_label.set_tooltip_text(text)

    def _set_pill(self, text, cls):
        sc = self.status_label.get_style_context()
        for c in set(PILL_CLASS.values()) | {"pill-disabled"}:
            sc.remove_class(c)
        self.status_label.set_text(text)
        if cls:
            sc.add_class(cls)

    def _set_urgency(self, urgent):
        sc = self.update_btn.get_style_context()
        if urgent:
            sc.add_class("urge")
        else:
            sc.remove_class("urge")


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Upkeep")
        self.set_icon_name(ICON_NAME)
        self.get_style_context().add_class("app-window")
        self.app = app
        self.cfg = config.load_config()
        self.busy = False
        self._checked = False
        self._pulse_id = None
        self._total = 0
        self._outdated = 0
        self._errors = 0
        self._last_check_time = ""
        self._last_summary = ""
        self._progress_text = ""
        self._stopped = ""
        self._banner_dismissed = False
        self._size_frac = (0.75, 0.72)
        self._apply_screen_size(initial=True)
        self.get_screen().connect("size-changed", self._on_screen_changed)
        self.get_screen().connect("monitors-changed", self._on_screen_changed)

        self.hb = Gtk.HeaderBar()
        self.hb.set_show_close_button(True)
        self.set_titlebar(self.hb)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        t = Gtk.Label(label="Upkeep", xalign=0)
        t.get_style_context().add_class("header-title")
        s = Gtk.Label(label="Manage AppImages from GitHub", xalign=0)
        s.get_style_context().add_class("header-subtitle")
        title_box.pack_start(t, False, False, 0)
        title_box.pack_start(s, False, False, 0)
        self.hb.set_custom_title(title_box)

        menu_btn = Gtk.MenuButton()
        menu_img = Gtk.Image.new_from_icon_name(ICON_MENU, Gtk.IconSize.BUTTON)
        menu_btn.set_image(menu_img)
        menu_btn.set_tooltip_text("Main menu")
        menu = Gtk.Menu()
        settings_item = Gtk.MenuItem(label="Settings…")
        settings_item.connect("activate", lambda *_: self.open_settings())
        menu.append(settings_item)
        about_item = Gtk.MenuItem(label="About Upkeep")
        about_item.connect("activate", lambda *_: self.show_about())
        menu.append(about_item)
        menu.show_all()
        menu_btn.set_popup(menu)
        self.hb.pack_end(menu_btn)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        self.banner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.banner_box.get_style_context().add_class("banner")
        self.banner_box.set_no_show_all(True)
        self.banner_label = Gtk.Label(label="", xalign=0)
        self.banner_label.set_hexpand(True)
        self.banner_box.pack_start(self.banner_label, True, True, 0)
        self.banner_btn = Gtk.Button(label="Update all")
        self.banner_btn.get_style_context().add_class("suggested-action")
        self.banner_btn.connect("clicked", lambda *_: self.update_all())
        self.banner_box.pack_start(self.banner_btn, False, False, 0)
        self.banner_close = _icon_btn(ICON_CLOSE, "Dismiss", ("flat",))
        self.banner_close.connect("clicked", lambda *_: self.dismiss_banner())
        self.banner_box.pack_start(self.banner_close, False, False, 0)
        self.banner_box.set_visible(False)
        vbox.pack_start(self.banner_box, False, False, 0)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.get_style_context().add_class("action-bar")

        self.check_btn = _flat_btn("Check", ICON_CHECK)
        self.check_btn.connect("clicked", lambda *_: self.run_checks())
        bar.pack_start(self.check_btn, False, False, 0)

        # go-down-symbolic, not download-symbolic: Adwaita has no
        # download-symbolic, and Adwaita is the icon theme the AppImage
        # ships, so the icon GTK cannot find is drawn as a filled box.
        self.update_all_btn = _btn_with_icon("Update all", ICON_UPDATE_ALL, ("suggested-action",))
        self.update_all_btn.connect("clicked", lambda *_: self.update_all())
        bar.pack_start(self.update_all_btn, False, False, 0)

        add_btn = _flat_btn("Add", ICON_ADD)
        add_btn.connect("clicked", lambda *_: self.add_app())
        bar.pack_start(add_btn, False, False, 0)

        self.status_label = Gtk.Label(label="Last check: never", xalign=1)
        self.status_label.get_style_context().add_class("status-label")
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        bar.pack_end(self.status_label, False, False, 0)
        vbox.pack_start(bar, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(False)
        self.progress.set_valign(Gtk.Align.CENTER)
        self.progress.set_no_show_all(True)
        self.progress.set_visible(False)
        vbox.pack_start(self.progress, False, False, 0)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-activated", lambda _, row: self.edit_app(row))
        self.listbox.connect("key-press-event", self._on_list_key)
        self.listbox.get_style_context().add_class("app-list")
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.listbox)
        scrolled.set_no_show_all(True)
        self.scrolled = scrolled
        vbox.pack_start(scrolled, True, True, 0)

        self.empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.empty_box.set_valign(Gtk.Align.CENTER)
        self.empty_box.set_no_show_all(True)
        pix = get_app_pixbuf(96)
        if pix is not None:
            self.empty_box.pack_start(Gtk.Image.new_from_pixbuf(pix), False, False, 0)
        empty_title = Gtk.Label(label="No AppImages configured")
        empty_title.get_style_context().add_class("empty-title")
        empty_title.set_margin_top(8)
        self.empty_box.pack_start(empty_title, False, False, 0)
        empty_sub = Gtk.Label(
            label="Add your first AppImage: Upkeep checks GitHub releases\nand keeps it up to date automatically."
        )
        empty_sub.get_style_context().add_class("empty-sub")
        empty_sub.set_justify(Gtk.Justification.CENTER)
        empty_sub.set_margin_bottom(8)
        self.empty_box.pack_start(empty_sub, False, False, 0)
        empty_btn = _btn_with_icon("Add your first AppImage", ICON_ADD, ("suggested-action",))
        empty_btn.connect("clicked", lambda *_: self.add_app())
        empty_btn.set_halign(Gtk.Align.CENTER)
        self.empty_box.pack_start(empty_btn, False, False, 0)
        vbox.pack_start(self.empty_box, True, False, 0)

        self.rebuild_list()

    def _on_list_key(self, _widget, event):
        """Delete removes, like every file manager the user has ever used."""
        if event.keyval != Gdk.KEY_Delete:
            return False
        row = self.listbox.get_selected_row()
        if isinstance(row, AppRow):
            self.delete_app(row)
            return True
        return False

    def show_about(self):
        about = Gtk.AboutDialog(transient_for=self, modal=True)
        about.set_program_name("Upkeep")
        about.set_version(__version__)
        about.set_comments("Automatically update AppImages from GitHub releases.")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_website("https://github.com/padelle2603/Upkeep")
        pix = get_app_pixbuf(128)
        if pix is not None:
            about.set_logo(pix)
        elif _icon_available():
            about.set_logo_icon_name(ICON_NAME)
        about.run()
        about.destroy()

    def show_update(self, version):
        """'Upkeep 1.1.0 is available', shown once per launch.

        Download hands over to the browser. Upkeep manages other people's
        AppImages, not itself: it never replaces its own binary. Not now just
        closes, nothing is remembered, and the check runs again next launch.
        """
        win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        win.set_title("Upkeep update")
        win.set_transient_for(self)
        win.set_default_size(460, -1)
        win.set_resizable(False)

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        not_now = _flat_btn("Not now", None)
        not_now.connect("clicked", lambda *_: win.destroy())
        header.pack_start(not_now)
        download = _btn_with_icon("Download", ICON_DOWNLOAD, ("suggested-action",))
        download.connect("clicked", lambda *_: (self._open_releases(), win.destroy()))
        header.pack_end(download)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        body.set_margin_start(20)
        body.set_margin_end(20)
        body.set_margin_top(8)
        body.set_margin_bottom(20)
        body.pack_start(
            Gtk.Image.new_from_icon_name(ICON_UPDATE_AVAILABLE, Gtk.IconSize.DIALOG),
            False, False, 0,
        )
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label=f"Upkeep {version} is available", xalign=0)
        title.get_style_context().add_class("empty-title")
        detail = Gtk.Label(
            label=(
                f"You are running {__version__}. Upkeep never updates itself — "
                "download the new version and replace the AppImage."
            ),
            xalign=0,
        )
        detail.set_line_wrap(True)
        detail.set_max_width_chars(46)
        detail.get_style_context().add_class("empty-sub")
        text.pack_start(title, False, False, 0)
        text.pack_start(detail, False, False, 0)
        body.pack_start(text, True, True, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.pack_start(header, False, False, 0)
        content.pack_start(body, True, True, 0)
        win.add(content)
        win.show_all()

    def _open_releases(self):
        try:
            subprocess.Popen(
                ["xdg-open", selfupdate.RELEASES_URL],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            self._notify("Could not open a browser. Visit " + selfupdate.RELEASES_URL)

    def _apply_screen_size(self, initial=False):
        screen = self.get_screen()
        monitor = screen.get_primary_monitor()
        try:
            win_mon = screen.get_monitor_at_window(self.get_window())
            if win_mon >= 0:
                monitor = win_mon
        except Exception:
            pass
        geo = screen.get_monitor_geometry(monitor)
        w = max(640, min(int(geo.width * self._size_frac[0]), 1280))
        h = max(440, min(int(geo.height * self._size_frac[1]), 900))
        if initial:
            self.set_default_size(w, h)
        else:
            cw, ch = self.get_size()
            if cw > geo.width or ch > geo.height:
                self.resize(min(w, geo.width), min(h, geo.height))
            elif geo.width * 0.95 > cw or geo.height * 0.95 > ch:
                self.resize(w, h)

    def _on_screen_changed(self, screen):
        self._apply_screen_size(initial=False)
        return False

    def rebuild_list(self):
        for child in list(self.listbox.get_children()):
            self.listbox.remove(child)
        apps = list(self.cfg["apps"])
        for a in apps:
            row = AppRow(a, self.cfg["settings"], self.update_row, self.edit_app, self.delete_app)
            self.listbox.add(row)
        has_apps = bool(apps)
        # show_all(), not set_visible(): these carry no_show_all so that
        # show() at startup does not flash them, and show_all() is the only
        # call that reaches their children.
        if has_apps:
            _reveal(self.scrolled)
        else:
            self.scrolled.hide()
        if has_apps:
            self.empty_box.hide()
        else:
            _reveal(self.empty_box)
        self.listbox.show_all()
        self.update_all_btn.set_sensitive(any(a.get("enabled", True) for a in apps))
        self.update_summary()

    def iter_rows(self):
        return [r for r in self.listbox.get_children() if isinstance(r, AppRow)]

    def update_summary(self):
        rows = self.iter_rows()
        self._total = len(rows)
        self._outdated = sum(1 for r in rows if r.status in ("outdated", "missing"))
        self._errors = sum(1 for r in rows if r.status == "error")
        self._refresh_banner()

    def dismiss_banner(self):
        self._banner_dismissed = True
        self.banner_box.hide()

    def _refresh_banner(self):
        """The one message that stays put: a stopped check and a pile of
        pending updates both disappear the moment the user acts on them,
        which is what a transient notification cannot do."""
        if self._banner_dismissed or self.busy:
            self.banner_box.hide()
            return
        if self._stopped:
            message, has_action = f"Check stopped: {self._stopped}", False
        elif self._outdated:
            message, has_action = updates_available(self._outdated), True
        else:
            self.banner_box.hide()
            return
        self.banner_label.set_text(message)
        # Reveal before hiding: _reveal() shows every child, including the
        # button a stopped check has no use for.
        _reveal(self.banner_box)
        if has_action:
            self.banner_btn.show_all()
        else:
            self.banner_btn.hide()

    def _render_status(self):
        if self.busy and self._progress_text:
            self.status_label.set_text(self._progress_text)
            return
        if not self._last_check_time:
            self.status_label.set_text("Last check: never")
            return
        text = f"Last check: {self._last_check_time}"
        if self._last_summary:
            text += f"  ·  {self._last_summary}"
        self.status_label.set_text(text)

    def set_busy(self, busy):
        self.busy = busy
        self.check_btn.set_sensitive(not busy)
        self.update_all_btn.set_sensitive(not busy)
        self._render_status()
        self._refresh_banner()

    def run_checks(self, auto=False):
        if self.busy:
            return
        self._stopped = ""
        self._banner_dismissed = False
        self.set_busy(True)
        self.set_progress_pulse(True, "Checking for updates…")
        rows = [r for r in self.iter_rows() if r.app.get("enabled", True)]

        def worker():
            results = []
            stopped = ""
            for row in rows:
                try:
                    r = updater.check_app(row.app, self.cfg["settings"])
                except Exception as e:
                    results.append((row, "error", None, _describe_exception(e), ""))
                    continue
                results.append((row, r.state, r.info, r.message, r.kind))
                if r.kind == "rate_limit":
                    # The hourly budget is per IP, so every remaining app would
                    # fail identically and spend requests the others need.
                    stopped = r.message
                    break
            GLib.idle_add(self.on_checks_done, results, auto, stopped)

        threading.Thread(target=worker, daemon=True).start()

    def on_checks_done(self, results, auto, stopped=""):
        self.set_busy(False)
        self.set_progress_pulse(False)
        self._checked = True
        outdated = 0
        errors = 0
        for row, state, info, message, _kind in results:
            row.set_status(state, info, message)
            if state in ("outdated", "missing"):
                outdated += 1
            elif state == "error":
                errors += 1
        self._stopped = stopped
        self.set_last_check(check_summary(len(results), outdated, errors))
        self.update_summary()
        if stopped:
            # The banner persists, a notification does not: a check that stops
            # for a reason the user cannot see looks like Upkeep is broken.
            self._notify("Upkeep: " + stopped)
        if auto and outdated:
            self._notify(f"{outdated} AppImage(s) to update")
        return False

    def update_all(self):
        if self.busy:
            return
        self.run_updates([r for r in self.iter_rows() if r.app.get("enabled", True)])

    def update_row(self, row):
        if self.busy or not row.app.get("enabled", True):
            return
        self.run_updates([row])

    def run_updates(self, rows):
        if not rows:
            return
        self.set_busy(True)
        self.set_progress_pulse(True, "Checking versions…")
        for row in rows:
            row.set_status("pending")

        def worker():
            outdated = []
            for row in rows:
                try:
                    r = updater.check_app(row.app, self.cfg["settings"])
                    if r.state in ("outdated", "missing"):
                        outdated.append((row, r.info, r.state == "missing"))
                    else:
                        GLib.idle_add(self.on_row_done, row, r.state, r.info, r.message)
                except Exception as e:
                    GLib.idle_add(self.on_row_done, row, "error", None, _describe_exception(e))
            GLib.idle_add(self._confirm_download, outdated)

        threading.Thread(target=worker, daemon=True).start()

    def _confirm_download(self, outdated):
        if not outdated:
            self.on_updates_done("No updates available")
            return False
        confirm_all = bool(self.cfg["settings"].get("confirm_download", True))
        confirmed = []
        for row, info, missing in outdated:
            if row.app.get("auto_update") or not confirm_all:
                confirmed.append(row)
                continue
            if self._ask_confirm(row.app, info, missing):
                confirmed.append(row)
            else:
                GLib.idle_add(self.on_row_done, row, "skipped", None)
        if not confirmed:
            self.on_updates_done("Update cancelled")
            return False
        self._download_worker(confirmed)
        return False

    def _download_worker(self, rows):
        total = len(rows)
        progress = [0]

        def worker():
            for row in rows:
                def progress_cb(done_bytes, total_bytes, row=row):
                    frac = (progress[0] + (done_bytes / total_bytes if total_bytes else 0)) / total
                    GLib.idle_add(self.set_progress_frac, frac, f"Downloading: {row.app['name']}")
                try:
                    r = updater.update_app(row.app, self.cfg["settings"], progress_cb=progress_cb, confirm_fn=None)
                    state, info, message = r.state, r.info, r.message
                except Exception as e:
                    state, info, message = "error", None, _describe_exception(e)
                progress[0] += 1
                GLib.idle_add(self.on_row_done, row, state, info, message)
            GLib.idle_add(self.on_updates_done)

        threading.Thread(target=worker, daemon=True).start()

    def _ask_confirm(self, app, info=None, missing=False):
        verb = "Reinstall" if missing else "Update"
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"{verb} {app['name']}?",
        )
        if missing:
            dlg.format_secondary_text("The AppImage executable was not found. The latest version will be downloaded.")
        elif info and info.get("tag"):
            dlg.format_secondary_text(f"Available version: {info.get('tag')}\n{info.get('asset_name') or ''}")
        else:
            dlg.format_secondary_text("A new version is available.")
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES

    def on_row_done(self, row, state, info=None, message=""):
        row.set_status(state, info, message)
        self._checked = True
        self.update_summary()
        return False

    def on_updates_done(self, message="Updates complete"):
        self.set_busy(False)
        self.set_progress_pulse(False)
        self._checked = True
        self.set_last_check(check_summary(self._total, self._outdated, self._errors))
        self.update_summary()
        self._notify(message)
        return False

    def set_last_check(self, summary=""):
        self._last_check_time = time.strftime("%H:%M")
        self._last_summary = summary
        self._render_status()

    def set_progress_frac(self, frac, text=""):
        if self._pulse_id:
            # A real fraction outranks the pulse: pulsing on top of it made
            # the bar flicker backwards for every byte received.
            GLib.source_remove(self._pulse_id)
            self._pulse_id = None
        _reveal(self.progress)
        self.progress.set_fraction(max(0.0, min(1.0, frac)))
        self._progress_text = text
        self._render_status()
        return False

    def set_progress_pulse(self, active, text=""):
        if active:
            _reveal(self.progress)
            self.progress.set_fraction(0.0)
            self._progress_text = text
            self._render_status()
            if self._pulse_id is None:
                self._pulse_id = GLib.timeout_add(120, self._pulse_step)
        else:
            if self._pulse_id:
                GLib.source_remove(self._pulse_id)
                self._pulse_id = None
            self._progress_text = ""
            self.progress.hide()
            self.progress.set_fraction(0.0)
            self._render_status()
        return False

    def _pulse_step(self):
        self.progress.pulse()
        return True

    def add_app(self):
        dlg = AppDialog(self, self.cfg)
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            self.cfg = config.load_config()
            self.rebuild_list()

    def edit_app(self, row):
        dlg = AppDialog(self, self.cfg, row.app)
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            self.cfg = config.load_config()
            self.rebuild_list()

    def delete_app(self, row):
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Remove '{row.app['name']}' from the configuration?",
        )
        dlg.format_secondary_text(row.path or "The installed file is left on disk.")
        resp = dlg.run()
        dlg.destroy()
        if resp == Gtk.ResponseType.YES:
            updater.remove_desktop_entry(row.app)
            self.cfg["apps"] = [a for a in self.cfg["apps"] if a["name"] != row.app["name"]]
            config.save_config(self.cfg)
            self.rebuild_list()

    def open_settings(self):
        dlg = SettingsDialog(self, self.cfg)
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            self.cfg = config.load_config()
            self.rebuild_list()

    def _notify(self, text):
        try:
            gi.require_version("Notify", "0.7")
            from gi.repository import Notify
            if not Notify.is_inited():
                Notify.init(APP_ID)
            Notify.Notification.new("Upkeep", text, ICON_NAME if _icon_available() else None).show()
        except Exception:
            pass


class UpdaterApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.win = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        theme.apply_theme()
        _load_css()
        Gtk.Window.set_default_icon_name(ICON_NAME)
        pix = get_app_pixbuf(64)
        if pix is not None:
            Gtk.Window.set_default_icon(pix)

    def do_activate(self):
        if self.win is not None:
            self.win.present()
            return
        self.win = MainWindow(self)
        self.win.show_all()
        threading.Thread(target=self._check_self, daemon=True).start()
        if self.win.cfg["settings"].get("check_on_startup", True):
            GLib.idle_add(self.win.run_checks, True)

    def _check_self(self):
        """One anonymous HEAD request, off the UI thread, silent on failure."""
        version = selfupdate.available_version(__version__)
        if version:
            GLib.idle_add(self.win.show_update, version)


def run():
    app = UpdaterApplication()
    try:
        app.run(None)
    except KeyboardInterrupt:
        pass