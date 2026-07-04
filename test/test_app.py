from typing import Any

import httpx
import pytest

from lm_remote.api_client import LMStudioClient
from lm_remote.app import LMStudioRemoteApp
from lm_remote.discovery import LMStudioServer
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, RichLog, Select, TabbedContent


async def _log_text(app: LMStudioRemoteApp, pilot: Pilot) -> str:
    # RichLog defers rendering until it is visible, so the Log tab must be
    # active before its writes actually populate `.lines`.
    app.query_one(TabbedContent).active = "tab-log"
    await pilot.pause()
    return "\n".join(str(line) for line in app.query_one("#log", RichLog).lines)


@pytest.fixture(autouse=True)
def no_network_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    # The app kicks off a network scan on mount; keep tests hermetic and fast
    # by making it a no-op unless a test overrides it.
    async def fake_discover_servers(*args: Any, **kwargs: Any) -> list[LMStudioServer]:
        return []

    monkeypatch.setattr("lm_remote.app.discover_servers", fake_discover_servers)
    monkeypatch.setattr("lm_remote.app.load_servers", lambda: [])
    monkeypatch.setattr("lm_remote.app.save_servers", lambda servers: None)


@pytest.mark.asyncio
async def test_app_mounts_and_lists_cached_servers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lm_remote.app.load_servers",
        lambda: [LMStudioServer(host="192.168.1.10"), LMStudioServer(host="192.168.1.20")],
    )
    app = LMStudioRemoteApp()
    async with app.run_test():
        select = app.query_one("#server-select", Select)
        values = [value for _, value in select._options if value is not Select.NULL]
        assert values == ["192.168.1.10:1234", "192.168.1.20:1234"]
        assert app.query_one("#load-btn", Button).disabled
        assert app.query_one("#disconnect-btn", Button).disabled


@pytest.mark.asyncio
async def test_connect_without_selecting_server_warns() -> None:
    app = LMStudioRemoteApp()
    async with app.run_test() as pilot:
        worker = app.connect()
        await worker.wait()
        assert "Choose a server first" in await _log_text(app, pilot)
        assert app.client is None


@pytest.mark.asyncio
async def test_connect_success_enables_controls_and_lists_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lm_remote.app.load_servers", lambda: [LMStudioServer(host="192.168.1.10")]
    )

    async def fake_list_models(self: LMStudioClient) -> list[dict[str, Any]]:
        return [
            {
                "type": "llm",
                "publisher": "openai",
                "key": "openai/gpt-oss-20b",
                "display_name": "GPT OSS 20B",
                "params_string": "20B",
                "size_bytes": 2_000_000_000,
                "format": "gguf",
                "loaded_instances": [],
            }
        ]

    monkeypatch.setattr(LMStudioClient, "list_models", fake_list_models)

    app = LMStudioRemoteApp()
    async with app.run_test():
        app.query_one("#server-select", Select).value = "192.168.1.10:1234"
        worker = app.connect()
        await worker.wait()

        assert app.client is not None
        assert app.query_one("#connect-btn", Button).disabled
        assert not app.query_one("#disconnect-btn", Button).disabled

        table = app.query_one("#models-table", DataTable)
        assert table.row_count == 1
        assert "openai/gpt-oss-20b" in app.models_by_key

        disconnect_worker = app.disconnect()
        await disconnect_worker.wait()
        assert app.client is None
        assert app.query_one("#models-table", DataTable).row_count == 0


@pytest.mark.asyncio
async def test_scan_network_populates_select_and_saves(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: list[LMStudioServer] = []

    async def fake_discover_servers(*args: Any, **kwargs: Any) -> list[LMStudioServer]:
        return [LMStudioServer(host="192.168.1.42")]

    monkeypatch.setattr("lm_remote.app.discover_servers", fake_discover_servers)
    monkeypatch.setattr("lm_remote.app.save_servers", lambda servers: saved.extend(servers))

    app = LMStudioRemoteApp()
    async with app.run_test() as pilot:
        # on_mount already triggered one scan; clear it and trigger a fresh one.
        saved.clear()
        worker = app.scan_network()
        await worker.wait()

        select = app.query_one("#server-select", Select)
        values = [value for _, value in select._options if value is not Select.NULL]
        assert values == ["192.168.1.42:1234"]
        assert saved == [LMStudioServer(host="192.168.1.42")]
        assert "Found 1 LM Studio server" in await _log_text(app, pilot)


@pytest.mark.asyncio
async def test_unload_dialog_warns_when_nothing_loaded() -> None:
    app = LMStudioRemoteApp()
    async with app.run_test() as pilot:
        app.open_unload_dialog()
        assert "No loaded instances to unload" in await _log_text(app, pilot)


@pytest.mark.asyncio
async def test_load_model_error_is_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    app = LMStudioRemoteApp()

    async def fake_load_model(self: LMStudioClient, model: str, **kwargs: Any) -> dict[str, Any]:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(LMStudioClient, "list_models", lambda self: [])
    monkeypatch.setattr(LMStudioClient, "load_model", fake_load_model)

    async with app.run_test() as pilot:
        app.client = LMStudioClient("http://127.0.0.1:1")
        worker = app.do_load_model({"model": "openai/gpt-oss-20b"})
        await worker.wait()
        assert "Load failed" in await _log_text(app, pilot)
