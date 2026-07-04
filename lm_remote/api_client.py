"""Async client for the LM Studio local REST API (v1).

Reference: https://lmstudio.ai/docs/developer/rest
"""

from __future__ import annotations

from typing import Any

import httpx


class LMStudioClient:
    def __init__(self, base_url: str, api_token: str | None = None, timeout: float = 30.0) -> None:
        headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
        self._client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_models(self) -> list[dict[str, Any]]:
        response = await self._client.get("/api/v1/models")
        response.raise_for_status()
        return response.json().get("models", [])

    async def load_model(
        self,
        model: str,
        *,
        context_length: int | None = None,
        eval_batch_size: int | None = None,
        flash_attention: bool | None = None,
        num_experts: int | None = None,
        offload_kv_cache_to_gpu: bool | None = None,
        echo_load_config: bool = True,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"model": model, "echo_load_config": echo_load_config}
        optional = {
            "context_length": context_length,
            "eval_batch_size": eval_batch_size,
            "flash_attention": flash_attention,
            "num_experts": num_experts,
            "offload_kv_cache_to_gpu": offload_kv_cache_to_gpu,
        }
        body.update({key: value for key, value in optional.items() if value is not None})

        response = await self._client.post("/api/v1/models/load", json=body)
        response.raise_for_status()
        return response.json()

    async def unload_model(self, instance_id: str) -> dict[str, Any]:
        response = await self._client.post(
            "/api/v1/models/unload", json={"instance_id": instance_id}
        )
        response.raise_for_status()
        return response.json()

    async def download_model(self, model: str, quantization: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"model": model}
        if quantization:
            body["quantization"] = quantization
        response = await self._client.post("/api/v1/models/download", json=body)
        response.raise_for_status()
        return response.json()

    async def download_status(self, job_id: str) -> dict[str, Any]:
        response = await self._client.get(f"/api/v1/models/download/status/{job_id}")
        response.raise_for_status()
        return response.json()
