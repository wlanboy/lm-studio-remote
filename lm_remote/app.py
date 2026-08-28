"""Textual TUI: discover LM Studio instances on the local network and drive
their REST API (list / load / unload)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

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

from lm_remote.api_client import LMStudioClient, LMStudioModel
from lm_remote.connection import ConnectionMixin
from lm_remote.discovery import LMStudioServer, load_servers
from lm_remote.discovery_ui import (
    HEALTH_CHECK_INTERVAL,
    HEALTH_ICON_UNKNOWN,
    ServerDiscoveryMixin,
)
from lm_remote.loading import LoadUnloadMixin
from lm_remote.models_table import ModelsTableMixin


class LMStudioRemoteApp(
    LoadUnloadMixin, ModelsTableMixin, ConnectionMixin, ServerDiscoveryMixin, App[None]
):
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
    #search-input {
        margin-bottom: 1;
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
    BINDINGS: ClassVar = [
        ("q", "quit", "Quit"),
        ("r", "refresh_models", "Refresh models"),
        ("l", "load_model", "Load"),
        ("u", "unload_model", "Unload"),
        ("s", "focus_search", "Search"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.servers: list[LMStudioServer] = load_servers()
        self.client: LMStudioClient | None = None
        self.models_by_key: dict[str, LMStudioModel] = {}
        self._all_models: list[LMStudioModel] = []
        self._sort_column_key: Any = None
        self._sort_reverse: bool = False
        self._connected_server: LMStudioServer | None = None
        self._server_health: dict[str, bool] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="connection-bar"):
            yield Label("LM Studio server:")
            yield Select(
                [(f"{HEALTH_ICON_UNKNOWN} {s.label}", s.label) for s in self.servers],
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
                yield Input(placeholder="Filter models... (s)", id="search-input")
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
            self.check_servers_health()
        self.scan_network()
        self.set_interval(HEALTH_CHECK_INTERVAL, self.check_servers_health)

    def log_message(self, message: str, level: str = "info") -> None:
        colors = {"info": "white", "warning": "yellow", "error": "bold red", "success": "green"}
        timestamp = datetime.now(tz=UTC).strftime("%H:%M:%S")
        style = colors.get(level, "white")
        self.query_one("#log", RichLog).write(f"[{style}][{timestamp}] {message}[/{style}]")
        if level in ("error", "warning"):
            self.notify(message, severity="error" if level == "error" else "warning")

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

    async def action_quit(self) -> None:
        if self.client is not None:
            await self.client.aclose()
        self.exit()


def run() -> None:
    LMStudioRemoteApp().run()


if __name__ == "__main__":
    run()
