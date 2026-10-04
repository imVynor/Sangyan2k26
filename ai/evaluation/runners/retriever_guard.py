"""Real-vs-mock retriever guard for SANGYAN benchmarks (Phase 7B).

A benchmark claiming to measure production retrieval must never silently run
against a mock. Detection is capability-based: the retriever must be (or
subclass) DefaultProvisionRetriever, expose the real retrieval channels, and
must not carry in-memory provisions or mock embedding providers. Class-name
heuristics are a secondary defence.
"""

from typing import Any

from ai.app.retrieval.retriever import DefaultProvisionRetriever


class MockRetrieverInRealBenchmarkError(RuntimeError):
    """Raised when a real-retrieval benchmark is wired to a mock/stub retriever."""


_REAL_CHANNELS = ("lexical_retriever", "vector_retriever", "citation_retriever", "scorer", "reranker")


def assert_real_retriever(retriever: Any) -> None:
    """Fail loudly unless `retriever` is the real PostgreSQL-backed hybrid retriever."""
    if retriever is None:
        raise MockRetrieverInRealBenchmarkError("No retriever configured: benchmark would receive empty retrieval.")

    cls_name = type(retriever).__name__
    module = type(retriever).__module__ or ""
    if "mock" in cls_name.lower() or "fake" in cls_name.lower() or "unittest.mock" in module:
        raise MockRetrieverInRealBenchmarkError(f"Mock/fake retriever detected: {module}.{cls_name}")

    if not isinstance(retriever, DefaultProvisionRetriever):
        raise MockRetrieverInRealBenchmarkError(
            f"Retriever {cls_name} is not a DefaultProvisionRetriever; real benchmark refuses to run."
        )

    missing = [c for c in _REAL_CHANNELS if getattr(retriever, c, None) is None]
    if missing:
        raise MockRetrieverInRealBenchmarkError(f"Retriever lacks real retrieval channels: {missing}")

    if getattr(retriever, "_in_memory_provisions", None):
        raise MockRetrieverInRealBenchmarkError("Retriever is running on in-memory provisions, not PostgreSQL.")

    provider = getattr(retriever, "embedding_provider", None)
    if provider is None or "mock" in type(provider).__name__.lower():
        raise MockRetrieverInRealBenchmarkError(f"Mock/missing embedding provider: {type(provider).__name__}")
