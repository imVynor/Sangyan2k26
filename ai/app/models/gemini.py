"""Gemini implementation of the provider-agnostic LLM interface."""

import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from ai.app.config.settings import settings
from ai.app.models.provider import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
)
from ai.app.models.schemas import LLMResponse, Message
from ai.app.utils.json_utils import parse_and_validate

T = TypeVar("T", bound=BaseModel)


class GeminiProvider(LLMProvider):
    """Small Gemini API client; API keys are sent in headers, never URLs or logs."""

    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        model_name: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("A non-empty Gemini API key is required.")
        self.api_key = api_key
        self.model_name = model_name or settings.gemini_model
        self.timeout = timeout or settings.response_generation_timeout
        self._external_client = client
        self._internal_client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        if self._internal_client is None or self._internal_client.is_closed:
            self._internal_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._internal_client

    async def close(self) -> None:
        """Close the internally managed HTTP connection pool."""
        if self._internal_client is not None and not self._internal_client.is_closed:
            await self._internal_client.aclose()
            self._internal_client = None

    async def check_health(self) -> bool:
        """Check the configured model endpoint without exposing the API key."""
        try:
            response = await self._get_client().get(
                f"/models/{self.model_name}",
                headers={"x-goog-api-key": self.api_key},
            )
            return response.is_success
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def generate(
        self,
        messages: list[Message],
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        system_text = "\n\n".join(m.content for m in messages if m.role == "system")
        contents = [
            {
                "role": "model" if message.role == "assistant" else "user",
                "parts": [{"text": message.content}],
            }
            for message in messages
            if message.role != "system"
        ]
        if not contents:
            raise LLMProviderError("Gemini requires at least one user or assistant message.")

        generation_config: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            generation_config["maxOutputTokens"] = max_tokens
        if response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = response_schema.model_json_schema()

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}

        started = time.perf_counter()
        try:
            response = await self._get_client().post(
                f"/models/{self.model_name}:generateContent",
                json=payload,
                headers={"x-goog-api-key": self.api_key},
            )
        except httpx.ConnectError as exc:
            raise LLMConnectionError("Could not connect to the Gemini API.") from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Gemini request timed out after {self.timeout}s.") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("Gemini request failed.") from exc

        if response.status_code == 404:
            raise LLMModelNotFoundError(f"Gemini model '{self.model_name}' was not found.")
        if not response.is_success:
            raise LLMProviderError(f"Gemini returned HTTP {response.status_code}.")

        try:
            data = response.json()
            candidates = data["candidates"]
            parts = candidates[0]["content"]["parts"]
            content = "".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMProviderError("Gemini returned an invalid or empty response.") from exc
        if not content:
            raise LLMProviderError("Gemini returned an empty response.")

        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount")
        completion_tokens = usage.get("candidatesTokenCount")
        return LLMResponse(
            content=content,
            model=self.model_name,
            provider="gemini",
            latency_ms=(time.perf_counter() - started) * 1000,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage.get("totalTokenCount"),
            raw_response=data,
        )

    async def generate_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> T:
        """Generate JSON and validate it against the requested Pydantic model."""
        response = await self.generate(
            messages=messages,
            response_schema=response_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return parse_and_validate(response.content, response_model)
