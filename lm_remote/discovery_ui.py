"""Network scan and health polling for known LM Studio servers, and the App
mixin that keeps the server-select dropdown and status label in sync."""

from __future__ import annotations

import asyncio
from typing import Protocol

from textual import work
from textual.widgets import Label, Select

from lm_remote.api_client import LMStudioClient
from lm_remote.discovery import (
    LMStudioServer,
    discover_servers,
    probe_health,
    save_servers,
)
from lm_remote.protocols import AppStateBase

HEALTH_CHECK_INTERVAL = 15.0
HEALTH_ICON_ONLINE = "\U0001f7e2"
HEALTH_ICON_OFFLINE = "\U0001f534"
HEALTH_ICON_UNKNOWN = "?"


class _DiscoveryAppState(AppStateBase, Protocol):
    """Attributes/methods `ServerDiscoveryMixin` needs from `LMStudioRemoteApp`."""

    servers: list[LMStudioServer]
    client: LMStudioClient | None
    _connected_server: LMStudioServer | None
    _server_health: dict[str, bool]

    # sibling members of `ServerDiscoveryMixin` itself
    def _health_icon(self, label: str) -> str: ...
    def _populate_server_select(self) -> None: ...
    def _update_status_label(self) -> None: ...
    def check_servers_health(self) -> object: ...


class ServerDiscoveryMixin:
    """Network discovery and health polling, mixed into `LMStudioRemoteApp`."""

    def _health_icon(self: _DiscoveryAppState, label: str) -> str:
        status = self._server_health.get(label)
        if status is None:
            return HEALTH_ICON_UNKNOWN
        return HEALTH_ICON_ONLINE if status else HEALTH_ICON_OFFLINE

    def _populate_server_select(self: _DiscoveryAppState) -> None:
        select = self.query_one("#server-select", Select)
        current = select.value
        options = [
            (f"{self._health_icon(server.label)} {server.label}", server.label)
            for server in self.servers
        ]
        select.set_options(options)
        if current is not Select.NULL and any(value == current for _, value in options):
            select.value = current

    def _update_status_label(self: _DiscoveryAppState) -> None:
        if self.client is None or self._connected_server is None:
            return
        icon = self._health_icon(self._connected_server.label)
        self.query_one("#status-label", Label).update(
            f"connected: {self._connected_server.label} {icon}"
        )

    @work(exclusive=True, group="health")
    async def check_servers_health(self: _DiscoveryAppState) -> None:
        servers = self.servers
        if not servers:
            self._server_health = {}
            return
        results = await asyncio.gather(*(probe_health(server) for server in servers))
        self._server_health = {server.label: ok for server, ok in zip(servers, results)}
        self._populate_server_select()
        self._update_status_label()

    @work(exclusive=True, group="discovery")
    async def scan_network(self: _DiscoveryAppState) -> None:
        self.log_message("Scanning local network for LM Studio servers...")
        found = await discover_servers()
        if found:
            known_tokens = {server.label: server.api_token for server in self.servers}
            for server in found:
                server.api_token = known_tokens.get(server.label)
            self.servers = found
            save_servers(found)
            self._populate_server_select()
            self.log_message(f"Found {len(found)} LM Studio server(s)", "success")
            self.check_servers_health()
        else:
            self.log_message("No LM Studio servers found on the local network", "warning")
