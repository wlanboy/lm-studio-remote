import httpx2
import pytest

from lm_remote.api_client import LMStudioClient, LoadModelParams


def make_client(handler, api_token: str | None = None) -> LMStudioClient:
    client = LMStudioClient("http://testserver", api_token=api_token)
    client._client = httpx2.AsyncClient(
        base_url="http://testserver",
        headers=client._client.headers,
        transport=httpx2.MockTransport(handler),
    )
    return client


@pytest.mark.asyncio
async def test_list_models_returns_models_array() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/models"
        return httpx2.Response(200, json={"models": [{"key": "a"}, {"key": "b"}]})

    client = make_client(handler)
    models = await client.list_models()
    assert [m.key for m in models] == ["a", "b"]
    await client.aclose()


@pytest.mark.asyncio
async def test_authorization_header_is_sent_when_token_given() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["authorization"] == "Bearer secret-token"
        return httpx2.Response(200, json={"models": []})

    client = make_client(handler, api_token="secret-token")
    await client.list_models()
    await client.aclose()


@pytest.mark.asyncio
async def test_load_model_sends_only_provided_optional_fields() -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        import json

        assert request.url.path == "/api/v1/models/load"
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "type": "llm",
                "instance_id": "openai/gpt-oss-20b",
                "load_time_seconds": 1.2,
                "status": "loaded",
            },
        )

    client = make_client(handler)
    params = LoadModelParams(model="openai/gpt-oss-20b", context_length=16384, flash_attention=True)
    result = await client.load_model(params)

    assert seen["body"] == {
        "model": "openai/gpt-oss-20b",
        "echo_load_config": True,
        "context_length": 16384,
        "flash_attention": True,
    }
    assert result["status"] == "loaded"
    await client.aclose()


@pytest.mark.asyncio
async def test_unload_model_posts_instance_id() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/api/v1/models/unload"
        import json

        assert json.loads(request.content) == {"instance_id": "openai/gpt-oss-20b"}
        return httpx2.Response(200, json={"instance_id": "openai/gpt-oss-20b"})

    client = make_client(handler)
    result = await client.unload_model("openai/gpt-oss-20b")
    assert result == {"instance_id": "openai/gpt-oss-20b"}
    await client.aclose()

@pytest.mark.asyncio
async def test_http_error_status_raises() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, json={"error": "boom"})

    client = make_client(handler)
    with pytest.raises(httpx2.HTTPStatusError):
        await client.list_models()
    await client.aclose()
