"""Textual TUI: discover LM Studio instances on the local network and drive
their REST API (list / load / unload)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    TabbedContent,
    TabPane,
)

from lm_remote.api_client import LMStudioClient
from lm_remote.discovery import LMStudioServer, discover_servers, load_servers, save_servers
from lm_remote.loading import LoadUnloadMixin


def _human_size(num_bytes: Any) -> str:
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


class LMStudioRemoteApp(LoadUnloadMixin, App[None]):
    TITLE = "LM Studio Remote"
    CSS = """
    #connection-bar {
        height: auto;
        padding: 1;
        background: $panel;
    }
    #connection-bar > * {
        margin-right: 1;
    }
    #server-select {
        width: 30;
    }
    #api-token {
        width: 16;
    }
    #status-label {
        width: 1fr;
        content-align: right middle;
    }
    .tab-toolbar {
        height: auto;
        padding-top: 1;
    }
    .tab-toolbar Button {
        margin-right: 1;
    }
    DataTable {
        height: 1fr;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_models", "Refresh models"),
        ("l", "load_model", "Load"),
        ("u", "unload_model", "Unload"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.servers: list[LMStudioServer] = load_servers()
        self.client: LMStudioClient | None = None
        self.models_by_key: dict[str, dict[str, Any]] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="connection-bar"):
            yield Label("LM Studio server:")
            yield Select(
                [(s.label, s.label) for s in self.servers],
                id="server-select",
                prompt="choose server",
            )
            yield Label("API token:")
            yield Input(placeholder="optional", password=True, id="api-token")
            yield Button("Connect", id="connect-btn", variant="success")
            yield Button("Disconnect", id="disconnect-btn", variant="error", disabled=True)
            yield Button("Scan network", id="scan-btn")
            yield Label("disconnected", id="status-label")
        with TabbedContent():
            with TabPane("Models", id="tab-models"):
                yield DataTable(id="models-table", cursor_type="row")
                with Horizontal(classes="tab-toolbar"):
                    yield Button("Refresh", id="refresh-models-btn", disabled=True)
                    yield Button("Load selected", id="load-btn", disabled=True)
                    yield Button("Unload...", id="unload-btn", disabled=True)
            with TabPane("Log", id="tab-log"):
                yield RichLog(id="log", wrap=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        models_table = self.query_one("#models-table", DataTable)
        models_table.add_columns(
            "Type", "Publisher", "Key", "Name", "Params", "Size", "Format", "Loaded"
        )
        if self.servers:
            self.log_message(f"Loaded {len(self.servers)} cached LM Studio server(s)")
        self.scan_network()

    def log_message(self, message: str, level: str = "info") -> None:
        colors = {"info": "white", "warning": "yellow", "error": "bold red", "success": "green"}
        timestamp = datetime.now().strftime("%H:%M:%S")
        style = colors.get(level, "white")
        self.query_one("#log", RichLog).write(f"[{style}][{timestamp}] {message}[/{style}]")
        if level in ("error", "warning"):
            self.notify(message, severity="error" if level == "error" else "warning")

    def set_connected_controls(self, connected: bool) -> None:
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

    # -- connection lifecycle -------------------------------------------------

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "connect-btn": self.connect,
            "disconnect-btn": self.disconnect,
            "scan-btn": self.scan_network,
            "refresh-models-btn": self.refresh_models,
            "load-btn": self.open_load_dialog,
            "unload-btn": self.open_unload_dialog,
        }
        handler = handlers.get(event.button.id or "")
        if handler is not None:
            handler()

    def _populate_server_select(self) -> None:
        select = self.query_one("#server-select", Select)
        current = select.value
        options = [(server.label, server.label) for server in self.servers]
        select.set_options(options)
        if current is not Select.NULL and any(value == current for _, value in options):
            select.value = current

    @work(exclusive=True, group="discovery")
    async def scan_network(self) -> None:
        self.log_message("Scanning local network for LM Studio servers...")
        found = await discover_servers()
        if found:
            self.servers = found
            save_servers(found)
            self._populate_server_select()
            self.log_message(f"Found {len(found)} LM Studio server(s)", "success")
        else:
            self.log_message("No LM Studio servers found on the local network", "warning")

    @work(exclusive=True)
    async def connect(self) -> None:
        label = self.query_one("#server-select", Select).value
        if label is Select.NULL or not label:
            self.log_message("Choose a server first", "warning")
            return
        server = next((s for s in self.servers if s.label == label), None)
        if server is None:
            self.log_message("Selected server is no longer known, rescan the network", "error")
            return

        api_token = self.query_one("#api-token", Input).value.strip() or None
        status_label = self.query_one("#status-label", Label)
        status_label.update(f"connecting to {server.label}...")
        self.log_message(f"Connecting to {server.base_url}")

        self.client = LMStudioClient(server.base_url, api_token=api_token)
        status_label.update(f"connected: {server.label}")
        self.set_connected_controls(True)
        self.log_message("Connected", "success")
        self.refresh_models()

    @work(exclusive=True)
    async def disconnect(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None
        self.set_connected_controls(False)
        self.query_one("#status-label", Label).update("disconnected")
        self.query_one("#models-table", DataTable).clear()
        self.models_by_key.clear()
        self.log_message("Disconnected")

    # -- models ---------------------------------------------------------------

    def action_refresh_models(self) -> None:
        self.refresh_models()

    @work(exclusive=True, group="models")
    async def refresh_models(self) -> None:
        if self.client is None:
            return
        try:
            models = await self.client.list_models()
        except (httpx.HTTPError, OSError) as exc:
            self.log_message(f"Failed to list models: {exc}", "error")
            return

        self.models_by_key = {model["key"]: model for model in models}
        table = self.query_one("#models-table", DataTable)
        table.clear()
        for model in models:
            loaded = model.get("loaded_instances") or []
            cells = (
                model.get("type", "-"),
                model.get("publisher", "-"),
                model.get("key", "-"),
                model.get("display_name", "-"),
                model.get("params_string", "-"),
                _human_size(model.get("size_bytes")),
                model.get("format") or "-",
                str(len(loaded)) if loaded else "-",
            )
            if loaded:
                cells = tuple(Text(str(cell), style="bold green") for cell in cells)
            table.add_row(*cells, key=model.get("key"))
        self.log_message(f"Loaded {len(models)} model(s)")

    async def action_quit(self) -> None:
        if self.client is not None:
            await self.client.aclose()
        self.exit()


def run() -> None:
    LMStudioRemoteApp().run()


if __name__ == "__main__":
    run()
