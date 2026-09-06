"""Connect / disconnect lifecycle and the App mixin that drives it."""

from __future__ import annotations

from typing import Protocol

from textual import work
from textual.widgets import Button, DataTable, Input, Label, Select

from lm_remote.api_client import LMStudioClient, LMStudioModel
from lm_remote.discovery import LMStudioServer, find_by_label, save_servers
from lm_remote.protocols import AppStateBase


class _ConnectionAppState(AppStateBase, Protocol):
    """Attributes/methods `ConnectionMixin` needs from `LMStudioRemoteApp`."""

    servers: list[LMStudioServer]
    client: LMStudioClient | None
    models_by_key: dict[str, LMStudioModel]
    _all_models: list[LMStudioModel]
    _connected_server: LMStudioServer | None

    def refresh_models(self) -> object: ...
    def _update_status_label(self) -> None: ...

    # sibling member of `ConnectionMixin` itself
    def set_connected_controls(self, connected: bool) -> None: ...


class ConnectionMixin:
    """Connect/disconnect lifecycle, mixed into `LMStudioRemoteApp`."""

    def on_select_changed(self: _ConnectionAppState, event: Select.Changed) -> None:
        if event.select.id != "server-select":
            return
        server = find_by_label(self.servers, event.value)
        self.query_one("#api-token", Input).value = (server.api_token if server else None) or ""

    def set_connected_controls(self: _ConnectionAppState, connected: bool) -> None:
        self.query_one("#connect-btn", Button).disabled = connected
        self.query_one("#disconnect-btn", Button).disabled = not connected
        self.query_one("#server-select", Select).disabled = connected
        self.query_one("#api-token", Input).disabled = connected
        for widget_id in (
            "refresh-models-btn",
            "load-btn",
            "unload-btn",
        ):
            self.query_one(f"#{widget_id}", Button).disabled = not connected

    @work(exclusive=True)
    async def connect(self: _ConnectionAppState) -> None:
        label = self.query_one("#server-select", Select).value
        if label is Select.NULL or not label:
            self.log_message("Choose a server first", "warning")
            return
        server = find_by_label(self.servers, label)
        if server is None:
            self.log_message("Selected server is no longer known, rescan the network", "error")
            return

        api_token = self.query_one("#api-token", Input).value.strip() or None
        status_label = self.query_one("#status-label", Label)
        status_label.update(f"connecting to {server.label}...")
        self.log_message(f"Connecting to {server.base_url}")

        server.api_token = api_token
        save_servers(self.servers)

        self.client = LMStudioClient(server.base_url, api_token=api_token)
        self._connected_server = server
        self._update_status_label()
        self.set_connected_controls(True)
        self.log_message("Connected", "success")
        self.refresh_models()

    @work(exclusive=True)
    async def disconnect(self: _ConnectionAppState) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None
        self._connected_server = None
        self.set_connected_controls(False)
        self.query_one("#status-label", Label).update("disconnected")
        self.query_one("#models-table", DataTable).clear()
        self.query_one("#search-input", Input).value = ""
        self.models_by_key.clear()
        self._all_models = []
        self.log_message("Disconnected")
