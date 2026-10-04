"""Ollama LLM Provider implementation using Ollama's HTTP API.

Adheres strictly to architectural requirements:
- Uses HTTP API (no shell/CLI calls).
- Provider-agnostic interface (does not leak Ollama specifics).
- Supports plain text and schema-guided structured output.
- Explicit failures for invalid or malformed outputs.
"""

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
from ai.app.utils.logging import log_llm_event

T = TypeVar("T", bound=BaseModel)


class OllamaProvider(LLMProvider):
    """Ollama implementation of LLMProvider via HTTP API."""

    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model_name = model_name
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.timeout = timeout or settings.default_request_timeout
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
        """Close underlying HTTP client if internally managed."""
        if self._internal_client is not None and not self._internal_client.is_closed:
            await self._internal_client.aclose()
            self._internal_client = None

    async def __aenter__(self) -> "OllamaProvider":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def check_health(self) -> bool:
        """Verify that Ollama server is reachable."""
        client = self._get_client()
        try:
            response = await client.get("/api/tags")
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def list_models(self) -> list[str]:
        """Fetch list of model names currently available in Ollama."""
        client = self._get_client()
        try:
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            return [m.get("name", "") for m in models if "name" in m]
        except httpx.ConnectError as exc:
            raise LLMConnectionError(f"Cannot reach Ollama at {self.base_url}") from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Ollama request timed out while listing models") from exc
        except Exception as exc:
            raise LLMProviderError(f"Failed to list Ollama models: {exc}") from exc

    async def is_model_available(self, model_name: str | None = None) -> bool:
        """Check if target model is installed in Ollama."""
        target = model_name or self.model_name
        models = await self.list_models()
        return any(m == target or m.startswith(f"{target}:") for m in models)

    async def generate(
        self,
        messages: list[Message],
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate response via Ollama /api/chat."""
        client = self._get_client()
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        if response_schema is not None:
            # Enforce schema constraint via Ollama structured format
            payload["format"] = response_schema.model_json_schema()

        start_time = time.perf_counter()
        log_llm_event(
            event="request_start",
            model=self.model_name,
            extra={"structured": response_schema is not None},
        )

        try:
            response = await client.post("/api/chat", json=payload)
        except httpx.ConnectError as exc:
            log_llm_event("request_failure", model=self.model_name, success=False, extra={"error": "Connection error"})
            raise LLMConnectionError(f"Could not connect to Ollama at {self.base_url}") from exc
        except httpx.TimeoutException as exc:
            log_llm_event("request_failure", model=self.model_name, success=False, extra={"error": "Timeout"})
            raise LLMTimeoutError(f"Ollama request timed out after {self.timeout}s") from exc
        except Exception as exc:
            log_llm_event("request_failure", model=self.model_name, success=False, extra={"error": str(exc)})
            raise LLMProviderError(f"Unexpected error communicating with Ollama: {exc}") from exc

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if response.status_code == 404:
            log_llm_event("request_failure", model=self.model_name, latency_ms=elapsed_ms, success=False, extra={"status": 404})
            raise LLMModelNotFoundError(f"Model '{self.model_name}' not found on Ollama instance")

        if response.status_code != 200:
            log_llm_event("request_failure", model=self.model_name, latency_ms=elapsed_ms, success=False, extra={"status": response.status_code})
            raise LLMProviderError(f"Ollama returned HTTP {response.status_code}: {response.text}")

        data = response.json()
        message_data = data.get("message", {})
        content = message_data.get("content", "")

        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")
        total_tokens = None
        if prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        log_llm_event(
            event="request_end",
            model=self.model_name,
            latency_ms=elapsed_ms,
            success=True,
            extra={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        )

        return LLMResponse(
            content=content,
            model=self.model_name,
            provider="ollama",
            latency_ms=elapsed_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            raw_response=data,
        )

    async def generate_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> T:
        """Generate and strictly validate structured output against Pydantic schema."""
        response = await self.generate(
            messages=messages,
            response_schema=response_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        try:
            validated = parse_and_validate(response.content, response_model)
            return validated
        except Exception as exc:
            log_llm_event(
                event="validation_failure",
                model=self.model_name,
                latency_ms=response.latency_ms,
                success=False,
                extra={"error": str(exc), "schema": response_model.__name__},
            )
            raise
