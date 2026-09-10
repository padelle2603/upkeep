# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .. import config


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, cfg):
        super().__init__(title="Settings", transient_for=parent, modal=True, flags=0)
        self.set_default_size(480, -1)
        self.cfg = cfg

        box = self.get_content_area()
        box.set_spacing(8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)

        def add_field(label, widget):
            hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lab = Gtk.Label(label=label, xalign=0)
            lab.set_size_request(160, -1)
            hb.pack_start(lab, False, False, 0)
            hb.pack_start(widget, True, True, 0)
            box.pack_start(hb, False, False, 0)

        self.dir_entry = Gtk.Entry()
        self.dir_entry.set_text(config.expand(cfg["settings"].get("default_install_dir")) or "")
        dir_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dir_row.pack_start(self.dir_entry, True, True, 0)
        btn = Gtk.Button(label="Browse")
        btn.get_style_context().add_class("ghost-btn")
        btn.connect("clicked", self._pick)
        dir_row.pack_start(btn, False, False, 0)
        add_field("Default folder", dir_row)

        self.tracker_entry = Gtk.Entry()
        self.tracker_entry.set_text(config.expand(cfg["settings"].get("tracker_dir")) or "~/.cache")
        add_field("Version tracker folder", self.tracker_entry)

        self.check_start = Gtk.CheckButton(label="Check for updates on startup")
        self.check_start.set_active(bool(cfg["settings"].get("check_on_startup", True)))
        box.pack_start(self.check_start, False, False, 0)

        self.confirm = Gtk.CheckButton(label="Ask for confirmation before downloading")
        self.confirm.set_active(bool(cfg["settings"].get("confirm_download", True)))
        box.pack_start(self.confirm, False, False, 0)

        self.create_desktop = Gtk.CheckButton(label="Create a .desktop entry for every installed/updated app")
        self.create_desktop.set_active(bool(cfg["settings"].get("create_desktop", True)))
        box.pack_start(self.create_desktop, False, False, 0)

        arch_hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.x86_check = Gtk.CheckButton(label="x86_64")
        self.arm_check = Gtk.CheckButton(label="aarch64")
        self.any_check = Gtk.CheckButton(label="Any")
        default_arch = cfg["settings"].get("default_arch", "x86_64")
        for cb, val in ((self.x86_check, "x86_64"), (self.arm_check, "aarch64"), (self.any_check, "any")):
            cb.connect("toggled", self._arch_toggled, val)
            if default_arch == val:
                cb.set_active(True)
            arch_hb.pack_start(cb, False, False, 0)
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lab = Gtk.Label(label="Default architecture", xalign=0)
        lab.set_size_request(160, -1)
        hb.pack_start(lab, False, False, 0)
        hb.pack_start(arch_hb, False, False, 0)
        box.pack_start(hb, False, False, 0)

        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.ACCEPT)
        self.get_widget_for_response(Gtk.ResponseType.ACCEPT).get_style_context().add_class("primary-btn")
        self.set_default_response(Gtk.ResponseType.ACCEPT)
        self.show_all()

    def _pick(self, _w):
        dlg = Gtk.FileChooserDialog(
            title="Select folder", transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.ACCEPT)
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            self.dir_entry.set_text(dlg.get_filename())
        dlg.destroy()

    def _arch_toggled(self, cb, val):
        if not cb.get_active():
            return
        for other in (self.x86_check, self.arm_check, self.any_check):
            if other is not cb:
                other.set_active(False)

    def _selected_arch(self):
        for cb, val in ((self.x86_check, "x86_64"), (self.arm_check, "aarch64"), (self.any_check, "any")):
            if cb.get_active():
                return val
        return "x86_64"

    def run(self):
        resp = super().run()
        if resp == Gtk.ResponseType.ACCEPT:
            self.cfg["settings"]["default_install_dir"] = self.dir_entry.get_text().strip() or "~/.local/share/applications/Appimages"
            self.cfg["settings"]["tracker_dir"] = self.tracker_entry.get_text().strip() or "~/.cache"
            self.cfg["settings"]["check_on_startup"] = self.check_start.get_active()
            self.cfg["settings"]["confirm_download"] = self.confirm.get_active()
            self.cfg["settings"]["create_desktop"] = self.create_desktop.get_active()
            self.cfg["settings"]["default_arch"] = self._selected_arch()
            config.save_config(self.cfg)
        self.destroy()
        return resp
