"""Embedding Provider Abstraction for SANGYAN Semantic Indexing.

Epistemic foundation:
- Abstract protocol allows swapping local models (Ollama nomic-embed-text),
  cloud providers (Gemini/OpenAI), or in-memory mock embeddings without changing retrieval logic.
- Dimension, model_id, and model_version are explicitly stamped on every embedding.
"""

import hashlib
import json
import logging
import math
from typing import Protocol, runtime_checkable
from urllib.error import URLError
import urllib.request

logger = logging.getLogger("sangyan.retrieval.embeddings")


class EmbeddingProviderUnavailable(RuntimeError):
    """Raised when the configured embedding service cannot generate vectors."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding generation providers."""

    @property
    def model_id(self) -> str:
        ...

    @property
    def model_version(self) -> str:
        ...

    @property
    def dimension(self) -> int:
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Compute dense vector representations for a batch of strings."""
        ...


class OllamaEmbeddingProvider:
    """Ollama-based local embedding provider using models like nomic-embed-text."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_id: str = "nomic-embed-text",
        model_version: str = "v1.5",
        dimension: int = 768,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._model_id = model_id
        self._model_version = model_version
        self._dimension = dimension
        self.timeout = timeout

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # Try batch endpoint /api/embed first
        try:
            req_data = json.dumps({"model": self._model_id, "input": texts}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/embed",
                data=req_data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                embeddings = result.get("embeddings", [])
                if len(embeddings) == len(texts):
                    return embeddings
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            logger.debug(f"Ollama /api/embed failed, falling back to /api/embeddings: {e}")

        # Fallback to single item /api/embeddings sequentially
        embeddings: list[list[float]] = []
        for text in texts:
            req_data = json.dumps({"model": self._model_id, "prompt": text}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/embeddings",
                data=req_data,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    emb = result.get("embedding", [])
                    embeddings.append(emb)
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                raise EmbeddingProviderUnavailable(
                    f"Ollama at {self.base_url} could not generate embeddings with model "
                    f"'{self._model_id}': {exc}"
                ) from exc

        return embeddings


class MockEmbeddingProvider:
    """Deterministic pseudo-embedding provider for offline unit tests.
    
    Generates unit-normalized pseudo-random vectors based on SHA-256 of text,
    guaranteeing 100% reproducible similarity without network or GPU.
    """

    def __init__(
        self,
        model_id: str = "mock-embed-v1",
        model_version: str = "1.0",
        dimension: int = 128,
    ) -> None:
        self._model_id = model_id
        self._model_version = model_version
        self._dimension = dimension

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for t in texts:
            # Hash text into deterministic pseudo-vector
            vec = []
            h = hashlib.sha256(t.encode("utf-8")).digest()
            for i in range(self._dimension):
                byte_val = h[i % len(h)]
                # Map byte to [-1.0, 1.0]
                val = ((byte_val / 127.5) - 1.0) * math.sin((i + 1) * 0.1)
                vec.append(val)
            # L2 normalize
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            results.append([x / norm for x in vec])
        return results
