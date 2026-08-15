"""
ConnectView - Server connection tools and access controls.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gtk

from hosty.shared.backend.server_manager import ServerInfo, ServerManager

from .mixins import LocalIpMixin, PlayersMixin
from .utils import *


class ConnectView(Gtk.Box, LocalIpMixin, PlayersMixin):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._server_info: ServerInfo | None = None
        self._server_manager: ServerManager | None = None
        self._manager_changed_id: int | None = None
        self._local_ip_rows: list[Adw.ActionRow] = []
        self._local_ip_value = _("Not available")
        self._whitelist_status_rows: list[Adw.ActionRow] = []
        self._whitelist_toggle_rows: list[Adw.SwitchRow] = []
        self._suppress_whitelist_toggle = False
        self._whitelist_groups: list[Adw.PreferencesGroup] = []
        self._banned_groups: list[Adw.PreferencesGroup] = []
        self._player_rows_by_group: dict[Gtk.Widget, list[Gtk.Widget]] = {}
        self._whitelist_list_rows: list[Adw.ExpanderRow] = []
        self._banned_list_rows: list[Adw.ExpanderRow] = []

        self._banner = Adw.Banner()
        self._banner.set_title(_("Restart the server to apply changes"))
        self._banner.set_button_label(_("Dismiss"))
        self._banner.set_revealed(False)
        self._banner.connect("button-clicked", lambda b: b.set_revealed(False))
        self.append(self._banner)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        page = Adw.PreferencesPage()
        page.add(self._make_local_network_group())
        self._append_players_groups(page)

        scrolled.set_child(page)
        self.append(scrolled)

        self._refresh_local_ip_row()

    def set_server(self, server_info: ServerInfo, server_manager: ServerManager):
        if self._server_manager and self._manager_changed_id is not None:
            try:
                self._server_manager.disconnect(self._manager_changed_id)
            except Exception:
                pass
            self._manager_changed_id = None

        self._server_info = server_info
        self._server_manager = server_manager

        self._manager_changed_id = self._server_manager.connect("server-changed", self._on_server_changed)
        self._refresh_local_ip_row()
        self._banner.set_revealed(False)
        self._refresh_whitelist_status()
        self._refresh_player_lists()

    def _on_server_changed(self, _manager, server_id):
        if not self._server_info or server_id != self._server_info.id:
            return
        self._refresh_whitelist_status()
        self._refresh_player_lists()

    def _server_dir(self) -> Path | None:
        if not self._server_info:
            return None
        return Path(self._server_info.server_dir)

    def _refresh_whitelist_status(self):
        enabled = False
        if self._server_manager and self._server_info:
            cfg = self._server_manager.get_config(self._server_info.id)
            if cfg:
                cfg.load()
                enabled = cfg.get_bool("white-list", False)

        self._suppress_whitelist_toggle = True
        for row in self._whitelist_toggle_rows:
            row.set_active(enabled)
        self._suppress_whitelist_toggle = False

    def _on_whitelist_toggled(self, row, _pspec):
        if self._suppress_whitelist_toggle:
            return
        if not self._server_manager or not self._server_info:
            return

        cfg = self._server_manager.get_config(self._server_info.id)
        if cfg:
            cfg.load()
            cfg.set_value("white-list", row.get_active())
            cfg.save()

        process = self._server_manager.get_process(self._server_info.id)
        self._banner.set_revealed(bool(process and process.is_running))

        self._server_manager.emit_on_main_thread("server-changed", self._server_info.id)

    def _server_running(self) -> bool:
        if not self._server_manager or not self._server_info:
            return False
        process = self._server_manager.get_process(self._server_info.id)
        return bool(process and process.is_running)

    def _alert(self, title: str, body: str):
        d = Adw.AlertDialog()
        d.set_heading(title)
        d.set_body(body)
        d.add_response("ok", _("OK"))
        d.present(self.get_root())

    def _toast(
        self,
        message: str,
        button_label: str | None = None,
        on_button=None,
        timeout: int = 3,
    ):
        root = self.get_root()
        if root and hasattr(root, "show_toast"):
            root.show_toast(
                message,
                button_label=button_label,
                on_button=on_button,
                timeout=timeout,
            )
