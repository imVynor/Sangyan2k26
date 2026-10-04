"""Vector Retrieval over SANGYAN Knowledge Provisions.

Epistemic foundation:
- Pure semantic similarity channel.
- Uses configured EmbeddingProvider (Ollama nomic-embed-text or Mock).
- Delegates persistence and cosine computation to ProvisionEmbeddingStore.
- Preserves score in [0.0, 1.0].
"""

import logging
from typing import Sequence
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from ai.app.knowledge.provisions import Provision
from ai.app.retrieval.contracts import RetrievalQuery
from ai.app.retrieval.embedding_provider import EmbeddingProvider
from ai.app.retrieval.embedding_store import ProvisionEmbeddingStore

logger = logging.getLogger("sangyan.retrieval.vector")


class VectorRetriever:
    """Dense vector retrieval engine using PostgreSQL embeddings."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        store: ProvisionEmbeddingStore | None = None,
    ) -> None:
        self.provider = provider
        self.store = store or ProvisionEmbeddingStore(provider=provider)

    async def retrieve(
        self,
        query: RetrievalQuery,
        limit: int = 30,
        session: AsyncSession | None = None,
        in_memory_provisions: Sequence[Provision] | None = None,
    ) -> list[tuple[str, float]]:
        """Retrieve candidates semantically. Returns list of (provision_id, semantic_score)."""
        # Formulate query text for embedding
        query_parts: list[str] = []
        if query.issue:
            query_parts.append(query.issue)
        if query.disputed_action:
            query_parts.append(query.disputed_action)
        if query.query_text:
            query_parts.append(query.query_text)
        if query.instrument_or_service:
            query_parts.append(f"regarding {query.instrument_or_service}")
        if query.key_terms:
            query_parts.append(" ".join(query.key_terms))

        full_query = " ".join(query_parts).strip()
        if not full_query:
            return []

        if in_memory_provisions is None and not await self.store.has_indexed_embeddings(session):
            return []

        # Generate query embedding
        query_vectors = self.provider.embed([full_query])
        if not query_vectors or not query_vectors[0]:
            return []
        q_vec = query_vectors[0]

        # In-memory evaluation if provisions supplied
        if in_memory_provisions is not None:
            return self._retrieve_in_memory(q_vec, in_memory_provisions, limit)

        # Execute PostgreSQL cosine similarity search
        return await self.store.search_similar(query_vector=q_vec, top_k=limit, session=session)

    def _retrieve_in_memory(
        self,
        query_vector: list[float],
        provisions: Sequence[Provision],
        limit: int,
    ) -> list[tuple[str, float]]:
        """In-memory cosine similarity for offline tests."""
        texts = [f"{p.title or ''} {p.source_text}".strip() for p in provisions]
        prov_vectors = self.provider.embed(texts)
        if not prov_vectors:
            return []

        q = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q) or 1.0
        q = q / q_norm

        mat = np.array(prov_vectors, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms

        sims = np.dot(mat, q)
        norm_sims = (sims + 1.0) / 2.0

        ranked = np.argsort(norm_sims)[::-1][:limit]
        return [(provisions[idx].provision_id, float(norm_sims[idx])) for idx in ranked]
