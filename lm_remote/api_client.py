"""Async client for the LM Studio local REST API (v1).

Reference: https://lmstudio.ai/docs/developer/rest
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx2


def auth_headers(api_token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_token}"} if api_token else {}


@dataclass
class LMStudioModel:
    key: str
    type: str = "-"
    publisher: str = "-"
    display_name: str = "-"
    params_string: str = "-"
    size_bytes: Any = None
    format: str | None = None
    loaded_instances: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> LMStudioModel:
        return cls(
            key=data.get("key", "-"),
            type=data.get("type", "-"),
            publisher=data.get("publisher", "-"),
            display_name=data.get("display_name", "-"),
            params_string=data.get("params_string", "-"),
            size_bytes=data.get("size_bytes"),
            format=data.get("format"),
            loaded_instances=data.get("loaded_instances") or [],
        )


@dataclass
class LoadModelParams:
    """Parameters for POST /api/v1/models/load, bundled so they travel as one
    value from the load dialog through to the request body."""

    model: str
    context_length: int | None = None
    eval_batch_size: int | None = None
    flash_attention: bool | None = None
    num_experts: int | None = None
    offload_kv_cache_to_gpu: bool | None = None
    echo_load_config: bool = True

    def to_request_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "echo_load_config": self.echo_load_config}
        optional = {
            "context_length": self.context_length,
            "eval_batch_size": self.eval_batch_size,
            "flash_attention": self.flash_attention,
            "num_experts": self.num_experts,
            "offload_kv_cache_to_gpu": self.offload_kv_cache_to_gpu,
        }
        body.update({key: value for key, value in optional.items() if value is not None})
        return body


class LMStudioClient:
    def __init__(self, base_url: str, api_token: str | None = None, timeout: float = 30.0) -> None:
        self._client = httpx2.AsyncClient(
            base_url=base_url, headers=auth_headers(api_token), timeout=timeout
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_models(self) -> list[LMStudioModel]:
        response = await self._client.get("/api/v1/models")
        response.raise_for_status()
        return [LMStudioModel.from_api(entry) for entry in response.json().get("models", [])]

    async def load_model(self, params: LoadModelParams) -> dict[str, Any]:
        response = await self._client.post("/api/v1/models/load", json=params.to_request_body())
        response.raise_for_status()
        return response.json()

    async def unload_model(self, instance_id: str) -> dict[str, Any]:
        response = await self._client.post(
            "/api/v1/models/unload", json={"instance_id": instance_id}
        )
        response.raise_for_status()
        return response.json()
