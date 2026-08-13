# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import threading
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from .. import config
from .. import updater
from .. import github


class AppDialog(Gtk.Dialog):
    def __init__(self, parent, cfg, app=None):
        super().__init__(
            title="Add AppImage" if app is None else f"Edit {app['name']}",
            transient_for=parent,
            modal=True,
            flags=0,
        )
        self.set_default_size(520, -1)
        self.cfg = cfg
        self.app = app or {}

        box = self.get_content_area()
        box.set_spacing(8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)

        def add_field(label, widget):
            hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lab = Gtk.Label(label=label, xalign=0)
            lab.set_size_request(140, -1)
            hb.pack_start(lab, False, False, 0)
            hb.pack_start(widget, True, True, 0)
            box.pack_start(hb, False, False, 0)

        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text("e.g. waywallen")
        if app:
            self.name_entry.set_text(app.get("name", ""))
        add_field("Name", self.name_entry)

        self.repo_entry = Gtk.Entry()
        self.repo_entry.set_placeholder_text("https://github.com/owner/repo  or  owner/repo")
        if app:
            self.repo_entry.set_text(app.get("repo", ""))
        add_field("GitHub repo", self.repo_entry)

        self.install_dir_entry = Gtk.Entry()
        if app and app.get("install_dir"):
            self.install_dir_entry.set_text(app["install_dir"])
        elif app:
            self.install_dir_entry.set_text(config.expand(cfg["settings"].get("default_install_dir")) or "")
        else:
            self.install_dir_entry.set_text(config.expand(cfg["settings"].get("default_install_dir")) or "")
        self.install_dir_entry.set_placeholder_text("Folder where future versions will be saved")
        dir_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dir_row.pack_start(self.install_dir_entry, True, True, 0)
        dir_btn = Gtk.Button(label="Browse")
        dir_btn.get_style_context().add_class("ghost-btn")
        dir_btn.connect("clicked", lambda *_: self._pick_folder(self.install_dir_entry))
        dir_row.pack_start(dir_btn, False, False, 0)
        add_field("Install folder", dir_row)

        self.custom_path_entry = Gtk.Entry()
        self.custom_path_entry.set_placeholder_text("Full path (optional, overrides folder+name)")
        if app and app.get("custom_path"):
            self.custom_path_entry.set_text(app["custom_path"])
        path_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        path_row.pack_start(self.custom_path_entry, True, True, 0)
        path_btn = Gtk.Button(label="Browse")
        path_btn.get_style_context().add_class("ghost-btn")
        path_btn.connect("clicked", lambda *_: self._pick_file(self.custom_path_entry))
        path_row.pack_start(path_btn, False, False, 0)
        add_field("Custom path", path_row)

        self.filter_entry = Gtk.Entry()
        self.filter_entry.set_placeholder_text("Regex to select the asset (optional)")
        if app and app.get("asset_filter"):
            self.filter_entry.set_text(app["asset_filter"])
        add_field("Asset filter", self.filter_entry)

        arch_hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.x86_check = Gtk.CheckButton(label="x86_64")
        self.arm_check = Gtk.CheckButton(label="aarch64")
        self.any_check = Gtk.CheckButton(label="Any")
        default_arch = app.get("arch") if app else cfg["settings"].get("default_arch", "x86_64")
        for cb, val in ((self.x86_check, "x86_64"), (self.arm_check, "aarch64"), (self.any_check, "any")):
            cb.connect("toggled", self._arch_toggled, val)
            if default_arch == val:
                cb.set_active(True)
            arch_hb.pack_start(cb, False, False, 0)
        add_field("Architecture", arch_hb)

        self.auto_check = Gtk.CheckButton(label="Update without asking for confirmation")
        self.auto_check.set_active(bool(app and app.get("auto_update")))
        box.pack_start(self.auto_check, False, False, 0)

        self.enabled_check = Gtk.CheckButton(label="Entry enabled")
        self.enabled_check.set_active(bool(app.get("enabled", True) if app else True))
        box.pack_start(self.enabled_check, False, False, 0)

        self.test_label = Gtk.Label(label="", xalign=0, wrap=True)
        self.test_label.set_justify(Gtk.Justification.LEFT)
        box.pack_start(self.test_label, False, False, 0)

        test_btn = Gtk.Button(label="Test: show latest release")
        test_btn.get_style_context().add_class("ghost-btn")
        test_btn.connect("clicked", lambda *_: self.test_repo())
        box.pack_start(test_btn, False, False, 0)

        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.ACCEPT)
        self.get_widget_for_response(Gtk.ResponseType.ACCEPT).get_style_context().add_class("primary-btn")
        self.set_default_response(Gtk.ResponseType.ACCEPT)
        self.show_all()

    def _arch_toggled(self, cb, val):
        if not cb.get_active():
            return
        for other in (self.x86_check, self.arm_check, self.any_check):
            if other is not cb:
                other.set_active(False)

    def _pick_folder(self, entry):
        dlg = Gtk.FileChooserDialog(
            title="Select folder", transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.ACCEPT)
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            entry.set_text(dlg.get_filename())
        dlg.destroy()

    def _pick_file(self, entry):
        dlg = Gtk.FileChooserDialog(
            title="Select AppImage file", transient_for=self, action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.ACCEPT)
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            entry.set_text(dlg.get_filename())
        dlg.destroy()

    def test_repo(self):
        repo = self.repo_entry.get_text().strip()
        if not repo:
            self.test_label.set_text("Enter a repository first.")
            return
        self.test_label.set_text("Checking...")
        arch = self._selected_arch()
        asset_filter = self.filter_entry.get_text().strip() or ""
        name = self.name_entry.get_text().strip() or ""

        def worker():
            try:
                info = updater.latest_info(config.normalize_app({"name": name or "x", "repo": repo, "arch": arch, "asset_filter": asset_filter}))
                text = f"Latest version: {info['tag']}\nSelected asset: {info['asset_name'] or 'NONE'} "
                if not info["asset_name"]:
                    text += "(no AppImage file found with current filters)"
            except github.GitHubError as e:
                text = f"Error: {e}"
            GLib.idle_add(self.test_label.set_text, text)

        threading.Thread(target=worker, daemon=True).start()

    def _selected_arch(self):
        for cb, val in ((self.x86_check, "x86_64"), (self.arm_check, "aarch64"), (self.any_check, "any")):
            if cb.get_active():
                return val
        return "x86_64"

    def run(self):
        resp = super().run()
        if resp == Gtk.ResponseType.ACCEPT:
            self._save()
        self.destroy()
        return resp

    def _save(self):
        name = self.name_entry.get_text().strip()
        repo = self.repo_entry.get_text().strip()
        if repo.startswith("http"):
            parts = [p for p in repo.split("/") if p]
            if len(parts) >= 2:
                repo = parts[-2] + "/" + parts[-1]
        old_name = self.app.get("name") if self.app else None
        if old_name and name != old_name:
            existing = [a for a in self.cfg["apps"] if a["name"] == name and a["name"] != old_name]
            if existing:
                name = old_name
        app = config.normalize_app({
            "name": name,
            "repo": repo,
            "install_dir": self.install_dir_entry.get_text().strip() or None,
            "custom_path": self.custom_path_entry.get_text().strip() or None,
            "asset_filter": self.filter_entry.get_text().strip(),
            "arch": self._selected_arch(),
            "auto_update": self.auto_check.get_active(),
            "enabled": self.enabled_check.get_active(),
        })
        for i, a in enumerate(self.cfg["apps"]):
            if a["name"] == self.app.get("name") or a["name"] == app["name"]:
                self.cfg["apps"][i] = app
                break
        else:
            self.cfg["apps"].append(app)
        config.save_config(self.cfg)
