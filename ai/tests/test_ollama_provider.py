"""Unit and integration tests for OllamaProvider."""

import json
import httpx
import pytest

from ai.app.models.ollama import OllamaProvider
from ai.app.models.provider import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)
from ai.app.models.schemas import CaseUnderstanding, Message
from ai.app.utils.json_utils import JSONParsingError, SchemaValidationError


def test_provider_initialization():
    provider = OllamaProvider(model_name="gemma4:12b")
    assert provider.model_name == "gemma4:12b"
    assert provider.base_url == "http://localhost:11434"
    assert provider.timeout == 120.0

    custom = OllamaProvider(
        model_name="custom_model",
        base_url="http://custom-host:8000/",
        timeout=45.0,
    )
    assert custom.model_name == "custom_model"
    assert custom.base_url == "http://custom-host:8000"
    assert custom.timeout == 45.0


@pytest.mark.asyncio
async def test_health_check_mock_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "gemma4:12b"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434")
    provider = OllamaProvider(model_name="gemma4:12b", client=client)

    assert await provider.check_health() is True
    models = await provider.list_models()
    assert models == ["gemma4:12b"]
    assert await provider.is_model_available("gemma4:12b") is True


@pytest.mark.asyncio
async def test_health_check_mock_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434")
    provider = OllamaProvider(model_name="gemma4:12b", client=client)

    assert await provider.check_health() is False
    with pytest.raises(LLMConnectionError):
        await provider.list_models()


@pytest.mark.asyncio
async def test_generate_text_mock():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        req_body = json.loads(request.read().decode())
        assert req_body["model"] == "gemma4:12b"
        assert req_body["messages"][0]["content"] == "Hello"
        return httpx.Response(
            200,
            json={
                "model": "gemma4:12b",
                "message": {"role": "assistant", "content": "Hello investor"},
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434")
    provider = OllamaProvider(model_name="gemma4:12b", client=client)

    response = await provider.generate(messages=[Message(role="user", content="Hello")])
    assert response.content == "Hello investor"
    assert response.model == "gemma4:12b"
    assert response.provider == "ollama"
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 5
    assert response.total_tokens == 15
    assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_generate_structured_success_mock():
    expected_case = {
        "intent": "report_debit",
        "entities": [{"name": "Zerodha", "category": "broker"}],
        "facts": [{"statement": "₹500 debited", "status": "USER_ASSERTED"}],
        "claims": [],
        "unknowns": [{"item": "Narration"}],
        "hypotheses": [],
        "next_question": "What was the remark?",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        req_body = json.loads(request.read().decode())
        assert "format" in req_body
        return httpx.Response(
            200,
            json={
                "model": "gemma4:12b",
                "message": {"role": "assistant", "content": json.dumps(expected_case)},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434")
    provider = OllamaProvider(model_name="gemma4:12b", client=client)

    result = await provider.generate_structured(
        messages=[Message(role="user", content="Test")],
        response_model=CaseUnderstanding,
    )
    assert isinstance(result, CaseUnderstanding)
    assert result.intent == "report_debit"
    assert result.entities[0].name == "Zerodha"
    assert result.facts[0].statement == "₹500 debited"


@pytest.mark.asyncio
async def test_generate_structured_malformed_json_rejection():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gemma4:12b",
                "message": {"role": "assistant", "content": "{malformed_json: not_quoted}"},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434")
    provider = OllamaProvider(model_name="gemma4:12b", client=client)

    with pytest.raises(JSONParsingError):
        await provider.generate_structured(
            messages=[Message(role="user", content="Test")],
            response_model=CaseUnderstanding,
        )


@pytest.mark.asyncio
async def test_generate_structured_schema_mismatch_rejection():
    def handler(request: httpx.Request) -> httpx.Response:
        # Valid JSON but missing required 'intent'
        return httpx.Response(
            200,
            json={
                "model": "gemma4:12b",
                "message": {"role": "assistant", "content": '{"entities": []}'},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434")
    provider = OllamaProvider(model_name="gemma4:12b", client=client)

    with pytest.raises(SchemaValidationError):
        await provider.generate_structured(
            messages=[Message(role="user", content="Test")],
            response_model=CaseUnderstanding,
        )


@pytest.mark.asyncio
async def test_model_not_found_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'nonexistent' not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434")
    provider = OllamaProvider(model_name="nonexistent", client=client)

    with pytest.raises(LLMModelNotFoundError):
        await provider.generate(messages=[Message(role="user", content="Test")])


# =====================================================================
# Live Integration Tests (Requires running Ollama)
# =====================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_ollama_health_and_generate():
    provider = OllamaProvider(model_name="gemma4:12b", timeout=60.0)
    try:
        is_healthy = await provider.check_health()
        if not is_healthy:
            pytest.skip("Local Ollama is not running.")

        models = await provider.list_models()
        if not any(m == "gemma4:12b" or m.startswith("gemma4:12b:") for m in models):
            pytest.skip("gemma4:12b is not installed in local Ollama.")

        resp = await provider.generate(
            messages=[Message(role="user", content="Respond with: pong")],
            temperature=0.0,
            max_tokens=100,
        )
        assert "pong" in resp.content.lower()
        assert resp.latency_ms > 0
    finally:
        await provider.close()
