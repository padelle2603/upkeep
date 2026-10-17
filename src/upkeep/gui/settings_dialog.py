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

from .widgets import browse_button, field, flat_button, section, switch_row, use_header


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, cfg):
        super().__init__(title="Settings", transient_for=parent, modal=True, flags=0)
        self.set_default_size(480, -1)
        self.cfg = cfg

        box = self.get_content_area()
        box.set_spacing(6)
        box.set_margin_top(4)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        box.pack_start(section("Folders"), False, False, 0)

        self.dir_entry = Gtk.Entry()
        self.dir_entry.set_text(config.expand(cfg["settings"].get("default_install_dir")) or "")
        dir_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dir_row.pack_start(self.dir_entry, True, True, 0)
        dir_row.pack_start(browse_button(self._pick), False, False, 0)
        box.pack_start(field("Default folder", dir_row), False, False, 0)

        self.tracker_entry = Gtk.Entry()
        self.tracker_entry.set_text(config.expand(cfg["settings"].get("tracker_dir")) or "~/.cache")
        box.pack_start(field("Version tracker folder", self.tracker_entry), False, False, 0)

        box.pack_start(section("Updates"), False, False, 0)

        row, self.check_start = switch_row(
            "Check for updates on startup",
            cfg["settings"].get("check_on_startup", True),
            subtitle="Ask GitHub for the newest release of every app when Upkeep opens",
        )
        box.pack_start(row, False, False, 0)

        row, self.confirm = switch_row(
            "Ask before downloading",
            cfg["settings"].get("confirm_download", True),
            subtitle="Apps marked as automatic are updated without a prompt",
        )
        box.pack_start(row, False, False, 0)

        row, self.create_desktop = switch_row(
            "Create a .desktop entry for every app",
            cfg["settings"].get("create_desktop", True),
            subtitle="Can be overridden per app",
        )
        box.pack_start(row, False, False, 0)

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
        box.pack_start(field("Default architecture", arch_hb), False, False, 0)

        box.pack_start(section("upkeep command"), False, False, 0)

        cli_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cli_labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="Add the upkeep command to PATH", xalign=0)
        title.get_style_context().add_class("switch-label")
        cli_labels.pack_start(title, False, False, 0)
        self.cli_status = Gtk.Label(xalign=0)
        self.cli_status.get_style_context().add_class("hint-label")
        cli_labels.pack_start(self.cli_status, False, False, 0)
        cli_row.pack_start(cli_labels, True, True, 0)
        self.cli_add = flat_button("Add", self._cli_add_clicked)
        cli_row.pack_start(self.cli_add, False, False, 0)
        self.cli_remove = flat_button("Remove", self._cli_remove_clicked)
        cli_row.pack_start(self.cli_remove, False, False, 0)
        box.pack_start(cli_row, False, False, 0)
        cli_path = Gtk.Label(
            label=f"Runs Upkeep from a terminal as: {updater.cli_command_path()}",
            xalign=0,
            wrap=True,
        )
        cli_path.get_style_context().add_class("hint-label")
        box.pack_start(cli_path, False, False, 0)
        self._refresh_cli_state()

        use_header(self)
        self.show_all()

    def _pick(self, _w):
        dlg = Gtk.FileChooserDialog(
            title="Select folder", transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.ACCEPT)
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            self.dir_entry.set_text(dlg.get_filename())
        dlg.destroy()

    def _refresh_cli_state(self):
        """Buttons follow the filesystem, so neither lies about what is there."""
        state = updater.cli_command_state()
        can_install = updater.running_appimage() is not None and state != "linked"
        self.cli_add.set_sensitive(can_install)
        # Only a link we created is ours to remove.
        self.cli_remove.set_sensitive(state == "linked")
        if state == "linked":
            self.cli_status.set_text(f"Linked to {updater.cli_command_target()}")
        elif state == "foreign":
            self.cli_status.set_text(
                f"{updater.cli_command_path()} holds a file that is not ours: left alone."
            )
        else:
            self.cli_status.set_text("Not installed.")
        if updater.running_appimage() is None:
            self.cli_add.set_tooltip_text(
                "Only available when Upkeep runs from its AppImage."
            )

    def _cli_add_clicked(self, _btn):
        ok, message = updater.set_cli_command(True)
        self._refresh_cli_state()
        if not ok:
            self._say(message, error=True)
            return
        notes = []
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

    def _cli_remove_clicked(self, _btn):
        ok, message = updater.set_cli_command(False)
        self._refresh_cli_state()
        if not ok:
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
