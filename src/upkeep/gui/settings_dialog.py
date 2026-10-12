# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .. import config
from .. import selfupdate
from .. import updater


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

        self.create_desktop = Gtk.CheckButton(label="Create a .desktop entry for every app (can be overridden per app)")
        self.create_desktop.set_active(bool(cfg["settings"].get("create_desktop", True)))
        box.pack_start(self.create_desktop, False, False, 0)

        self.cli_command = Gtk.CheckButton(label="Add the upkeep command to PATH")
        # State comes from the filesystem, not from a saved setting.
        self.cli_command.set_active(updater.cli_command_active())
        self.cli_command.set_sensitive(updater.running_appimage() is not None)
        if updater.running_appimage() is None:
            self.cli_command.set_tooltip_text(
                "Only available when Upkeep runs from its AppImage."
            )
        self.cli_command.connect("toggled", self._cli_toggled)
        box.pack_start(self.cli_command, False, False, 0)
        cli_hint = Gtk.Label(
            label=f"Runs Upkeep from a terminal as: {updater.cli_command_path()}",
            xalign=0,
        )
        cli_hint.get_style_context().add_class("dim-label")
        box.pack_start(cli_hint, False, False, 0)

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

    def _cli_toggled(self, cb):
        """Act on the click, not on Save.

        A switch that only takes effect when you close the dialog is a switch
        that lies. The filesystem is the source of truth, so a failure puts
        the box back where it was.
        """
        if getattr(self, "_cli_busy", False):
            return
        ok, message = updater.set_cli_command(cb.get_active())
        if ok:
            notes = []
            if cb.get_active():
                warning = updater.path_warning()
                if warning:
                    notes.append(warning)
                if self._manages_itself():
                    notes.append(
                        "Upkeep is also in your managed apps, so its .desktop "
                        "entry is rewritten on every update and will stop "
                        "pointing at the upkeep command.\n\n"
                        "Remove it with:  upkeep remove Upkeep\n"
                        "You will still be told when a new version is out."
                    )
            if notes:
                self._say("\n\n".join([message] + notes), warning=True)
            return
        self._cli_busy = True
        cb.set_active(not cb.get_active())
        self._cli_busy = False
        self._say(message, error=True)

    def _manages_itself(self):
        """True when Upkeep also sits in its own config as a managed app.

        In that case write_desktop_entry rewrites upkeep.desktop on every
        update, so the menu entry stops pointing at the upkeep command.
        """
        for app in self.cfg.get("apps") or []:
            if (app.get("repo") or "").lower() == selfupdate.SELF_REPO.lower():
                if app.get("create_desktop", True):
                    return True
        return False

    def _say(self, text, error=False, warning=False):
        """Friendly dialog instead of a crash or a silent no-op."""
        if not text:
            return
        kind = Gtk.MessageType.ERROR if error else (
            Gtk.MessageType.WARNING if warning else Gtk.MessageType.INFO
        )
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=kind,
            buttons=Gtk.ButtonsType.OK,
            text="upkeep command",
        )
        dlg.format_secondary_text(text)
        dlg.run()
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
