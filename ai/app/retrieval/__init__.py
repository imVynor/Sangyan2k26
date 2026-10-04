"""SANGYAN Hybrid Provision Retrieval Package.

Epistemic foundation:
- Provision-level atomic retrieval preserving statutory authority and provenance.
- Hybrid fusion of Lexical (PostgreSQL tsvector), Dense Vector (pgvector embeddings), Exact Citation, and Authority Routing.
- Deterministic multi-factor reranking and explicit failure states.
"""

from ai.app.retrieval.context_builder import ContextBuilder
from ai.app.retrieval.contracts import (
    HybridRetrievalConfig,
    RetrievalCandidate,
    RetrievalFailureReason,
    RetrievalMode,
    RetrievalQuery,
    RetrievalResponse,
    RetrievalResult,
)
from ai.app.retrieval.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderUnavailable,
    MockEmbeddingProvider,
    OllamaEmbeddingProvider,
)
from ai.app.retrieval.embedding_store import (
    ProvisionEmbeddingStore,
    compute_content_hash,
)
from ai.app.retrieval.lexical import LexicalRetriever
from ai.app.retrieval.reranker import DeterministicReranker
from ai.app.retrieval.retriever import DefaultProvisionRetriever, ProvisionRetriever
from ai.app.retrieval.scoring import HybridScorer
from ai.app.retrieval.vector import VectorRetriever

__all__ = [
    "ContextBuilder",
    "DefaultProvisionRetriever",
    "EmbeddingProvider",
    "EmbeddingProviderUnavailable",
    "HybridRetrievalConfig",
    "HybridScorer",
    "LexicalRetriever",
    "MockEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "ProvisionEmbeddingStore",
    "ProvisionRetriever",
    "RetrievalCandidate",
    "RetrievalFailureReason",
    "RetrievalMode",
    "RetrievalQuery",
    "RetrievalResponse",
    "RetrievalResult",
    "VectorRetriever",
    "compute_content_hash",
]
