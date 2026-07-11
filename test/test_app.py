from typing import Any

import httpx
import pytest

from lm_remote.api_client import LMStudioClient
from lm_remote.app import LMStudioRemoteApp
from lm_remote.discovery import LMStudioServer
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, RichLog, Select, TabbedContent


async def _log_text(app: LMStudioRemoteApp, pilot: Pilot) -> str:
    # RichLog defers rendering until it is visible, so the Log tab must be
    # active before its writes actually populate `.lines`.
    app.query_one(TabbedContent).active = "tab-log"
    await pilot.pause()
    return "\n".join(str(line) for line in app.query_one("#log", RichLog).lines)


@pytest.fixture(autouse=True)
def no_network_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    # The app kicks off a network scan and health checks on mount; keep tests
    # hermetic and fast by making them no-ops unless a test overrides them.
    async def fake_discover_servers(*args: Any, **kwargs: Any) -> list[LMStudioServer]:
        return []

    async def fake_probe_health(*args: Any, **kwargs: Any) -> bool:
        return True

    monkeypatch.setattr("lm_remote.app.discover_servers", fake_discover_servers)
    monkeypatch.setattr("lm_remote.app.load_servers", lambda: [])
    monkeypatch.setattr("lm_remote.app.save_servers", lambda servers: None)
    monkeypatch.setattr("lm_remote.app.probe_health", fake_probe_health)


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
async def test_header_click_sorts_models_table(monkeypatch: pytest.MonkeyPatch) -> None:
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
            },
            {
                "type": "llm",
                "publisher": "meta",
                "key": "meta/llama-3-8b",
                "display_name": "Llama 3 8B",
                "params_string": "8B",
                "size_bytes": 8_000_000_000,
                "format": "gguf",
                "loaded_instances": [],
            },
        ]

    monkeypatch.setattr(LMStudioClient, "list_models", fake_list_models)

    app = LMStudioRemoteApp()
    async with app.run_test() as pilot:
        app.query_one("#server-select", Select).value = "192.168.1.10:1234"
        worker = app.connect()
        await worker.wait()

        table = app.query_one("#models-table", DataTable)
        publisher_column = next(
            key for key, column in table.columns.items() if str(column.label) == "Publisher"
        )

        def click_publisher_header() -> None:
            column = table.columns[publisher_column]
            app.on_data_table_header_selected(
                DataTable.HeaderSelected(table, publisher_column, 1, column.label)
            )

        # Ascending click: "meta" sorts before "openai".
        click_publisher_header()
        await pilot.pause()
        assert table.get_row_at(0)[2] == "meta/llama-3-8b"

        # Clicking the same header again reverses the order.
        click_publisher_header()
        await pilot.pause()
        assert table.get_row_at(0)[2] == "openai/gpt-oss-20b"

        # Re-populating the table (e.g. via refresh) preserves the active sort.
        worker = app.refresh_models()
        await worker.wait()
        assert table.get_row_at(0)[2] == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_search_filters_models_table(monkeypatch: pytest.MonkeyPatch) -> None:
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
            },
            {
                "type": "llm",
                "publisher": "meta",
                "key": "meta/llama-3-8b",
                "display_name": "Llama 3 8B",
                "params_string": "8B",
                "size_bytes": 8_000_000_000,
                "format": "gguf",
                "loaded_instances": [],
            },
        ]

    monkeypatch.setattr(LMStudioClient, "list_models", fake_list_models)

    app = LMStudioRemoteApp()
    async with app.run_test() as pilot:
        app.query_one("#server-select", Select).value = "192.168.1.10:1234"
        worker = app.connect()
        await worker.wait()

        table = app.query_one("#models-table", DataTable)
        assert table.row_count == 2

        # The "s" binding focuses the search field instead of doing nothing.
        await pilot.press("s")
        assert app.focused is app.query_one("#search-input", Input)

        await pilot.press("l", "l", "a", "m", "a")
        await pilot.pause()
        assert table.row_count == 1
        assert table.get_row_at(0)[2] == "meta/llama-3-8b"

        # Typing "s" while the search field is focused must type, not re-trigger the binding.
        search = app.query_one("#search-input", Input)
        search.value = ""
        await pilot.press("s")
        await pilot.pause()
        assert search.value == "s"
        # "s" matches "oss" in openai/gpt-oss-20b but not meta/llama-3-8b.
        assert table.row_count == 1
        assert table.get_row_at(0)[2] == "openai/gpt-oss-20b"

        search.value = ""
        await pilot.pause()
        assert table.row_count == 2


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
async def test_health_check_updates_select_icons(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lm_remote.app.load_servers",
        lambda: [LMStudioServer(host="192.168.1.10"), LMStudioServer(host="192.168.1.20")],
    )

    async def fake_probe_health(server: LMStudioServer) -> bool:
        return server.host == "192.168.1.10"

    monkeypatch.setattr("lm_remote.app.probe_health", fake_probe_health)

    app = LMStudioRemoteApp()
    async with app.run_test():
        worker = app.check_servers_health()
        await worker.wait()

        select = app.query_one("#server-select", Select)
        labels = {
            value: str(label) for label, value in select._options if value is not Select.NULL
        }
        assert labels["192.168.1.10:1234"].startswith("\U0001f7e2")
        assert labels["192.168.1.20:1234"].startswith("\U0001f534")


@pytest.mark.asyncio
async def test_connect_persists_api_token_and_prefills_on_reselect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lm_remote.app.load_servers", lambda: [LMStudioServer(host="192.168.1.10")]
    )
    saved: list[list[LMStudioServer]] = []
    monkeypatch.setattr(
        "lm_remote.app.save_servers", lambda servers: saved.append(list(servers))
    )

    async def fake_list_models(self: LMStudioClient) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(LMStudioClient, "list_models", fake_list_models)

    app = LMStudioRemoteApp()
    async with app.run_test() as pilot:
        select = app.query_one("#server-select", Select)
        select.value = "192.168.1.10:1234"
        await pilot.pause()
        app.query_one("#api-token", Input).value = "secret-token"

        worker = app.connect()
        await worker.wait()

        assert saved[-1][0].api_token == "secret-token"

        disconnect_worker = app.disconnect()
        await disconnect_worker.wait()

        # Deselecting and reselecting the server prefills the persisted token.
        select.value = Select.NULL
        await pilot.pause()
        select.value = "192.168.1.10:1234"
        await pilot.pause()
        assert app.query_one("#api-token", Input).value == "secret-token"


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
