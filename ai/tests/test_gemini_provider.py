"""Tests for Gemini's LLM provider adapter."""

import asyncio

import httpx
from pydantic import BaseModel

from ai.app.models.gemini import GeminiProvider
from ai.app.models.schemas import Message


def test_generate_sends_api_key_in_header_and_maps_text_response():
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Please share the deducted amount."}]}}
                ],
                "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 7, "totalTokenCount": 15},
            },
        )

    async def run() -> None:
        client = httpx.AsyncClient(
            base_url=GeminiProvider.base_url,
            transport=httpx.MockTransport(handle),
        )
        provider = GeminiProvider("test-key-not-real", client=client)
        result = await provider.generate(
            [
                Message(role="system", content="Be concise."),
                Message(role="user", content="Why did my holdings decrease?"),
            ],
            temperature=0.2,
            max_tokens=80,
        )
        assert result.content == "Please share the deducted amount."
        assert result.provider == "gemini"
        assert requests[0].headers["x-goog-api-key"] == "test-key-not-real"
        assert "test-key-not-real" not in str(requests[0].url)
        body = requests[0].read().decode()
        assert "Why did my holdings decrease?" in body
        assert '"systemInstruction"' in body
        await client.aclose()

    asyncio.run(run())


def test_generate_structured_validates_gemini_json():
    class ShortAnswer(BaseModel):
        answer: str

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": '{"answer":"Need the amount."}'}]}}]},
        )

    async def run() -> None:
        client = httpx.AsyncClient(
            base_url=GeminiProvider.base_url,
            transport=httpx.MockTransport(handle),
        )
        provider = GeminiProvider("test-key-not-real", client=client)
        result = await provider.generate_structured(
            [Message(role="user", content="What do you need?")],
            ShortAnswer,
        )
        assert result.answer == "Need the amount."
        await client.aclose()

    asyncio.run(run())
