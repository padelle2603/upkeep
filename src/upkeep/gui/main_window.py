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

from .app_dialog import AppDialog
from .settings_dialog import SettingsDialog

APP_ID = "io.github.padelle2603.upkeep"
ICON_NAME = "upkeep"


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
    theme = Gtk.IconTheme.get_default()
    try:
        info = theme.lookup_icon(ICON_NAME, size, Gtk.IconLookupFlags.USE_BUILTIN)
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
    "pending": "Checking\u2026",
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
DOT_CLASS = {
    "outdated": "dot-warn",
    "uptodate": "dot-ok",
    "updated": "dot-ok",
    "error": "dot-err",
    "missing": "dot-err",
    "skipped": "dot-neutral",
    "pending": "dot-accent",
}


def _btn_with_icon(label, icon, classes=()):
    btn = Gtk.Button(label=label)
    if icon:
        img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
        btn.set_image(img)
        btn.set_always_show_image(True)
    for c in classes:
        btn.get_style_context().add_class(c)
    return btn


def _plural(n, singular, plural=None):
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def check_summary(total, outdated, errors):
    """Human-readable outcome of a check, shown in the footer so the user always sees a result."""
    if not total:
        return "no apps to check"
    parts = [_plural(total, "app")]
    if outdated:
        parts.append(f"{_plural(outdated, 'update')} available")
    elif not errors:
        parts.append("all up to date")
    if errors:
        parts.append(_plural(errors, "error"))
    return "  ·  ".join(parts)


def _describe_exception(exc):
    return f"{type(exc).__name__}: {exc}"


class AppRow(Gtk.ListBoxRow):
    def __init__(self, app, settings, on_update, on_edit, on_delete):
        super().__init__()
        self.app = app
        self.status = "unknown"
        self.message = ""
        self.local_version = ""
        self.remote_tag = None
        self.installed = False
        self.get_style_context().add_class("app-card")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(14)
        box.set_margin_end(10)

        self.dot = Gtk.Label(label="\u25cf")
        self.dot.set_size_request(14, -1)
        box.pack_start(self.dot, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_hexpand(True)

        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.name_label = Gtk.Label(label=app["name"], xalign=0)
        self.name_label.get_style_context().add_class("app-name")
        name_row.pack_start(self.name_label, False, False, 0)
        repo_label = Gtk.Label(label=app["repo"], xalign=0)
        repo_label.get_style_context().add_class("app-repo")
        name_row.pack_start(repo_label, False, False, 0)
        info.pack_start(name_row, False, False, 0)

        self.sub_label = Gtk.Label(label="", xalign=0)
        self.sub_label.get_style_context().add_class("app-sub")
        self.sub_label.set_ellipsize(Pango.EllipsizeMode.END)
        info.pack_start(self.sub_label, False, False, 0)

        self.path_label = Gtk.Label(label="", xalign=0)
        self.path_label.get_style_context().add_class("app-path")
        self.path_label.set_ellipsize(Pango.EllipsizeMode.END)
        info.pack_start(self.path_label, False, False, 0)

        box.pack_start(info, True, True, 0)

        self.status_label = Gtk.Label(label="")
        self.status_label.get_style_context().add_class("status-pill")
        self.status_label.set_margin_start(8)
        box.pack_start(self.status_label, False, False, 0)

        update_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        update_btn.set_tooltip_text("Update")
        update_btn.get_style_context().add_class("update-btn")
        update_btn.connect("clicked", lambda *_: on_update(self))
        self.update_btn = update_btn
        box.pack_start(update_btn, False, False, 0)

        edit_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic", Gtk.IconSize.BUTTON)
        edit_btn.set_tooltip_text("Edit")
        edit_btn.get_style_context().add_class("icon-btn")
        edit_btn.connect("clicked", lambda *_: on_edit(self))
        box.pack_start(edit_btn, False, False, 0)

        delete_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
        delete_btn.set_tooltip_text("Remove")
        delete_btn.get_style_context().add_class("icon-btn")
        delete_btn.get_style_context().add_class("danger")
        delete_btn.connect("clicked", lambda *_: on_delete(self))
        box.pack_start(delete_btn, False, False, 0)

        self.add(box)
        self.refresh(settings)

    def refresh(self, settings):
        local = config.read_local_version(self.app, settings) or "not installed"
        self.local_version = local
        path = config.app_target_path(self.app)
        self.installed = os.path.exists(path)
        self.path_label.set_text(path)
        enabled = self.app.get("enabled", True)
        self.update_btn.set_sensitive(enabled)
        self.name_label.set_sensitive(not enabled)
        self.sub_label.set_sensitive(not enabled)
        self.path_label.set_sensitive(not enabled)
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
            self.sub_label.set_text(f"{local}  \u2192  {self.remote_tag}")
        else:
            self.sub_label.set_text(local)

    def _apply_status(self):
        ctx = self.get_style_context()
        enabled = self.app.get("enabled", True)
        if not enabled:
            ctx.add_class("disabled")
            self.update_btn.set_sensitive(False)
            self._set_pill("Disabled", "pill-disabled")
            self._set_dot("dot-neutral")
            self._set_reason("")
            return
        ctx.remove_class("disabled")
        self.update_btn.set_sensitive(True)
        self._set_pill(STATE_LABEL.get(self.status, ""), PILL_CLASS.get(self.status, ""))
        self._set_dot(DOT_CLASS.get(self.status, "dot-neutral"))
        self._set_reason(self.message if self.status in ("error", "missing") else "")

    def _set_reason(self, text):
        """Surface the reason (rate limit, missing file, ...) without breaking the layout."""
        self.status_label.set_tooltip_text(text)
        self.set_tooltip_text(text)

    def _set_pill(self, text, cls):
        sc = self.status_label.get_style_context()
        for c in set(PILL_CLASS.values()) | {"pill-disabled"}:
            sc.remove_class(c)
        self.status_label.set_text(text)
        if cls:
            sc.add_class(cls)

    def _set_dot(self, cls):
        sc = self.dot.get_style_context()
        for c in set(DOT_CLASS.values()):
            sc.remove_class(c)
        if cls:
            sc.add_class(cls)


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
        self._size_frac = (0.75, 0.72)
        self._apply_screen_size(initial=True)
        self.get_screen().connect("size-changed", self._on_screen_changed)
        self.get_screen().connect("monitors-changed", self._on_screen_changed)

        self.hb = Gtk.HeaderBar()
        self.hb.set_show_close_button(True)
        self.set_titlebar(self.hb)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if _icon_available():
            logo = Gtk.Image.new_from_icon_name(ICON_NAME, Gtk.IconSize.LARGE_TOOLBAR)
        else:
            pix = get_app_pixbuf(22)
            logo = Gtk.Image.new_from_pixbuf(pix) if pix else Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.LARGE_TOOLBAR)
        title_box.pack_start(logo, False, False, 0)
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        t = Gtk.Label(label="Upkeep", xalign=0)
        t.get_style_context().add_class("header-title")
        s = Gtk.Label(label="Manage AppImages from GitHub", xalign=0)
        s.get_style_context().add_class("header-subtitle")
        text_box.pack_start(t, False, False, 0)
        text_box.pack_start(s, False, False, 0)
        title_box.pack_start(text_box, False, False, 0)
        self.hb.set_custom_title(title_box)

        self.check_btn = _btn_with_icon("Check", "view-refresh-symbolic", ("ghost-btn",))
        self.check_btn.connect("clicked", lambda *_: self.run_checks())
        self.hb.pack_start(self.check_btn)

        self.update_all_btn = _btn_with_icon("Update all", "download-symbolic", ("primary-btn",))
        self.update_all_btn.connect("clicked", lambda *_: self.update_all())
        self.hb.pack_start(self.update_all_btn)

        add_btn = _btn_with_icon("Add", "list-add-symbolic", ("ghost-btn",))
        add_btn.connect("clicked", lambda *_: self.add_app())
        self.hb.pack_end(add_btn)

        settings_btn = Gtk.Button.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        settings_btn.set_tooltip_text("Settings")
        settings_btn.get_style_context().add_class("icon-btn")
        settings_btn.connect("clicked", lambda *_: self.open_settings())
        self.hb.pack_end(settings_btn)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        self.summary_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.summary_box.get_style_context().add_class("summary-strip")
        vbox.pack_start(self.summary_box, False, False, 0)
        self.stat_labels = {}
        self.summary_box.pack_start(self._stat_card("total", "Total apps", ""), False, False, 0)
        self.summary_box.pack_start(self._stat_card("outdated", "Updates available", "accent-warn"), False, False, 0)
        self.summary_box.pack_start(self._stat_card("ok", "Up to date", "accent-ok"), False, False, 0)
        self.summary_box.pack_start(self._stat_card("err", "Errors", "accent-err"), False, False, 0)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-activated", lambda _, row: self.edit_app(row))
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
        empty_sub = Gtk.Label(label="Add your first AppImage: the app checks GitHub releases\nand keeps it up to date automatically.")
        empty_sub.get_style_context().add_class("empty-sub")
        empty_sub.set_justify(Gtk.Justification.CENTER)
        empty_sub.set_margin_bottom(6)
        self.empty_box.pack_start(empty_sub, False, False, 0)
        empty_btn = _btn_with_icon("Add your first AppImage", "list-add-symbolic", ("primary-btn",))
        empty_btn.connect("clicked", lambda *_: self.add_app())
        self.empty_box.pack_start(empty_btn, False, False, 0)
        vbox.pack_start(self.empty_box, True, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer.set_margin_start(14)
        footer.set_margin_end(14)
        footer.set_margin_top(4)
        footer.set_margin_bottom(10)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        footer.pack_start(self.progress, True, True, 0)

        self.last_check_label = Gtk.Label(label="Last check: never")
        self.last_check_label.get_style_context().add_class("footer-label")
        footer.pack_end(self.last_check_label, False, False, 0)
        vbox.pack_start(footer, False, False, 0)

        self.rebuild_list()

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
        not_now = _btn_with_icon("Not now", None, ("ghost-btn",))
        not_now.connect("clicked", lambda *_: win.destroy())
        header.pack_start(not_now)
        download = _btn_with_icon("Download", None, ("primary-btn",))
        download.connect("clicked", lambda *_: (self._open_releases(), win.destroy()))
        header.pack_end(download)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        body.set_margin_start(20)
        body.set_margin_end(20)
        body.set_margin_top(8)
        body.set_margin_bottom(20)
        body.pack_start(
            Gtk.Image.new_from_icon_name("software-update-available-symbolic", Gtk.IconSize.DIALOG),
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

    def _stat_card(self, key, label, accent):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.get_style_context().add_class("stat-card")
        val = Gtk.Label(label="0", xalign=0)
        val.get_style_context().add_class("stat-value")
        if accent:
            val.get_style_context().add_class(accent)
        lab = Gtk.Label(label=label, xalign=0)
        lab.get_style_context().add_class("stat-label")
        card.pack_start(val, False, False, 0)
        card.pack_start(lab, False, False, 0)
        self.stat_labels[key] = val
        return card

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
        self.scrolled.set_visible(has_apps)
        self.empty_box.set_visible(not has_apps)
        self.listbox.show_all()
        self.update_all_btn.set_sensitive(any(a.get("enabled", True) for a in apps))
        self.update_summary()

    def iter_rows(self):
        return [r for r in self.listbox.get_children() if isinstance(r, AppRow)]

    def update_summary(self):
        rows = self.iter_rows()
        total = len(rows)
        outdated = sum(1 for r in rows if r.status in ("outdated", "missing"))
        ok = sum(1 for r in rows if r.status in ("uptodate", "updated"))
        err = sum(1 for r in rows if r.status == "error")
        self._set_stat("total", str(total))
        if self._checked and total:
            self._set_stat("outdated", str(outdated))
            self._set_stat("ok", str(ok))
            self._set_stat("err", str(err))
        else:
            self._set_stat("outdated", "\u2014")
            self._set_stat("ok", "\u2014")
            self._set_stat("err", "\u2014")

    def _set_stat(self, key, text):
        label = self.stat_labels.get(key)
        if label is not None:
            label.set_text(text)

    def set_busy(self, busy):
        self.busy = busy
        self.check_btn.set_sensitive(not busy)
        self.update_all_btn.set_sensitive(not busy)

    def run_checks(self, auto=False):
        if self.busy:
            return
        self.set_busy(True)
        self.set_progress_pulse(True, "Checking for updates...")
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
        self.set_last_check(check_summary(len(results), outdated, errors))
        self.update_summary()
        if stopped:
            # The footer persists, a notification does not: a check that stops
            # for a reason the user cannot see looks like Upkeep is broken.
            self.set_last_check(f"stopped · {stopped}")
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
        self.set_progress_pulse(True, "Checking versions...")
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
                    GLib.idle_add(self.set_progress_frac, frac, f"Download: {row.app['name']}")
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
        self.set_last_check()
        self.update_summary()
        self._notify(message)
        return False

    def set_last_check(self, summary=""):
        now = time.strftime("%H:%M")
        text = f"Last check: {now}"
        if summary:
            text += f"  ·  {summary}"
        self.last_check_label.set_text(text)

    def set_progress_frac(self, frac, text=""):
        self.progress.set_fraction(max(0.0, min(1.0, frac)))
        self.progress.set_text(text)
        return False

    def set_progress_pulse(self, active, text=""):
        if active:
            self.progress.set_fraction(0.0)
            self.progress.set_text(text)
            self._pulse_id = GLib.timeout_add(120, self._pulse_step)
        else:
            if self._pulse_id:
                GLib.source_remove(self._pulse_id)
                self._pulse_id = None
            self.progress.set_text("")
            self.progress.set_fraction(0.0)
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
