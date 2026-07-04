import ipaddress
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from lm_remote.discovery import (
    LMStudioServer,
    discover_servers,
    load_servers,
    save_servers,
)


def test_load_servers_returns_empty_list_when_file_missing(tmp_path: Path) -> None:
    assert load_servers(tmp_path / "does-not-exist.json") == []


def test_load_servers_returns_empty_list_on_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "lmstudioserver.json"
    path.write_text("not json")
    assert load_servers(path) == []


def test_save_and_load_servers_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "lmstudioserver.json"
    servers = [LMStudioServer(host="192.168.1.10"), LMStudioServer(host="192.168.1.20", port=5678)]

    save_servers(servers, path)

    assert json.loads(path.read_text()) == [
        {"host": "192.168.1.10", "port": 1234},
        {"host": "192.168.1.20", "port": 5678},
    ]
    assert load_servers(path) == servers


def test_lmstudioserver_label_and_base_url() -> None:
    server = LMStudioServer(host="10.0.0.5", port=1234)
    assert server.label == "10.0.0.5:1234"
    assert server.base_url == "http://10.0.0.5:1234"


@pytest.mark.asyncio
async def test_discover_servers_returns_empty_list_when_subnet_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lm_remote.discovery.local_subnet", lambda port=1234: None)
    assert await discover_servers() == []


@pytest.mark.asyncio
async def test_discover_servers_probes_network_and_finds_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    network = ipaddress.ip_network("10.0.0.0/30", strict=False)
    reachable_hosts = {"10.0.0.1"}

    async def fake_open_connection(host: str, port: int):
        if host not in reachable_hosts:
            raise OSError("connection refused")

        class FakeWriter:
            def close(self) -> None:
                return None

            async def wait_closed(self) -> None:
                return None

        return None, FakeWriter()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    original_async_client = httpx.AsyncClient

    def fake_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr("asyncio.open_connection", fake_open_connection)
    monkeypatch.setattr("lm_remote.discovery.httpx.AsyncClient", fake_async_client)

    servers = await discover_servers(network=network, port=1234)

    assert servers == [LMStudioServer(host="10.0.0.1", port=1234)]
