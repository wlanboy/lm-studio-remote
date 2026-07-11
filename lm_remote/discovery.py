"""Discover LM Studio REST API servers on the local network.

Scans the /24 subnet of the machine's default route for hosts answering on
the LM Studio REST API port, and caches hits in a JSON file so the app can
offer them in a dropdown without rescanning every time.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

DEFAULT_PORT = 1234
CONNECT_TIMEOUT = 0.3
HTTP_TIMEOUT = 1.5
CONCURRENCY = 128

SERVERS_FILE = Path.cwd() / "data" / "lmstudioserver.json"
SERVERS_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class LMStudioServer:
    host: str
    port: int = DEFAULT_PORT
    api_token: str | None = None

    @property
    def label(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def local_subnet(port: int = DEFAULT_PORT) -> ipaddress.IPv4Network | None:
    """Best-effort guess at the /24 network this machine's default route sits on."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            # UDP connect: no packet is actually sent, just picks the outbound
            # interface so we can read its local address.
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
        except OSError:
            return None
    return ipaddress.IPv4Network(f"{local_ip}/24", strict=False)


async def _probe(host: str, port: int, client: httpx.AsyncClient) -> LMStudioServer | None:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT
        )
    except (OSError, asyncio.TimeoutError):
        return None
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass

    try:
        response = await client.get(f"http://{host}:{port}/api/v1/models")
    except (httpx.HTTPError, OSError):
        return None
    if response.status_code != 200 or "models" not in response.json():
        return None
    return LMStudioServer(host=host, port=port)


async def discover_servers(
    network: ipaddress.IPv4Network | None = None, port: int = DEFAULT_PORT
) -> list[LMStudioServer]:
    """Scan the local /24 for reachable LM Studio REST API servers."""
    network = network if network is not None else local_subnet(port)
    if network is None:
        return []

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def bounded_probe(host: str, client: httpx.AsyncClient) -> LMStudioServer | None:
        async with semaphore:
            return await _probe(host, port, client)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        results = await asyncio.gather(
            *(bounded_probe(str(ip), client) for ip in network.hosts())
        )
    return [server for server in results if server is not None]


def load_servers(path: Path = SERVERS_FILE) -> list[LMStudioServer]:
    if not path.is_file():
        return []
    try:
        entries = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return [
        LMStudioServer(
            host=entry["host"],
            port=entry.get("port", DEFAULT_PORT),
            api_token=entry.get("api_token"),
        )
        for entry in entries
        if "host" in entry
    ]


def save_servers(servers: list[LMStudioServer], path: Path = SERVERS_FILE) -> None:
    # Omit api_token when unset so cached entries without a token keep the
    # same on-disk shape they had before tokens existed.
    entries = [
        {k: v for k, v in asdict(server).items() if not (k == "api_token" and v is None)}
        for server in servers
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))


async def probe_health(server: LMStudioServer, timeout: float = HTTP_TIMEOUT) -> bool:
    """Check whether a known server currently answers its REST API."""
    headers = {"Authorization": f"Bearer {server.api_token}"} if server.api_token else {}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{server.base_url}/api/v1/models", headers=headers)
    except (httpx.HTTPError, OSError):
        return False
    return response.status_code == 200
