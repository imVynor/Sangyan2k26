"""Embedding Storage and Cache Manager for SANGYAN Provisions.

Epistemic foundation:
- Content hash caching prevents redundant embedding computation.
- Model isolation: distinct embeddings maintained per model_id and model_version.
- Exact vector cosine similarity retrieval over PostgreSQL embeddings.
"""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Sequence
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ai.app.db.models import KnowledgeProvisionEmbeddingORM, KnowledgeProvisionORM
from ai.app.db.session import get_async_session
from ai.app.knowledge.provisions import Provision
from ai.app.retrieval.embedding_provider import EmbeddingProvider

logger = logging.getLogger("sangyan.retrieval.embedding_store")


def compute_content_hash(text_content: str) -> str:
    """Deterministic SHA-256 fingerprint of the embedded text."""
    return hashlib.sha256(text_content.encode("utf-8")).hexdigest()


class ProvisionEmbeddingStore:
    """Manages persistent embeddings and similarity search for KnowledgeProvisions."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    async def has_indexed_embeddings(self, session: AsyncSession | None = None) -> bool:
        """Check whether the active model has any indexed vectors before embedding a query."""
        stmt = (
            select(KnowledgeProvisionEmbeddingORM.id)
            .where(
                KnowledgeProvisionEmbeddingORM.embedding_model_id == self.provider.model_id,
                KnowledgeProvisionEmbeddingORM.embedding_model_version == self.provider.model_version,
            )
            .limit(1)
        )

        async def _run(s: AsyncSession) -> bool:
            return (await s.execute(stmt)).scalar_one_or_none() is not None

        if session is not None:
            return await _run(session)
        async with get_async_session() as s:
            return await _run(s)

    async def get_cached_content_hashes(
        self,
        session: AsyncSession,
    ) -> dict[str, str]:
        """Map of provision_id -> content_hash for the active embedding model."""
        stmt = select(
            KnowledgeProvisionEmbeddingORM.provision_id,
            KnowledgeProvisionEmbeddingORM.content_hash,
        ).where(
            KnowledgeProvisionEmbeddingORM.embedding_model_id == self.provider.model_id,
            KnowledgeProvisionEmbeddingORM.embedding_model_version == self.provider.model_version,
        )
        res = await session.execute(stmt)
        return {row[0]: row[1] for row in res.fetchall()}

    async def index_provisions(
        self,
        provisions: Sequence[Provision],
        session: AsyncSession | None = None,
        batch_size: int = 50,
    ) -> int:
        """Batch compute and persist embeddings for provisions requiring indexing."""
        if not provisions:
            return 0

        async def _run(s: AsyncSession) -> int:
            cached_hashes = await self.get_cached_content_hashes(s)
            to_embed: list[tuple[Provision, str]] = []

            for p in provisions:
                text_to_embed = f"{p.title or ''} {p.source_text}".strip()
                c_hash = compute_content_hash(text_to_embed)
                if p.provision_id not in cached_hashes or cached_hashes[p.provision_id] != c_hash:
                    to_embed.append((p, c_hash))

            if not to_embed:
                logger.info("All provisions already have up-to-date embeddings cached.")
                return 0

            logger.info(f"Computing embeddings for {len(to_embed)} provisions in batches of {batch_size}...")
            total_indexed = 0

            for i in range(0, len(to_embed), batch_size):
                batch = to_embed[i : i + batch_size]
                texts = [f"{p.title or ''} {p.source_text}".strip() for p, _ in batch]
                vectors = self.provider.embed(texts)

                now = datetime.now(timezone.utc)
                for (p, c_hash), vec in zip(batch, vectors):
                    emb_id = f"emb_{p.provision_id}_{self.provider.model_id}_{c_hash[:8]}"
                    # Delete existing if updating
                    await s.execute(
                        delete(KnowledgeProvisionEmbeddingORM).where(
                            KnowledgeProvisionEmbeddingORM.provision_id == p.provision_id,
                            KnowledgeProvisionEmbeddingORM.embedding_model_id == self.provider.model_id,
                            KnowledgeProvisionEmbeddingORM.embedding_model_version == self.provider.model_version,
                        )
                    )
                    orm_emb = KnowledgeProvisionEmbeddingORM(
                        id=emb_id,
                        provision_id=p.provision_id,
                        embedding=vec,
                        embedding_model_id=self.provider.model_id,
                        embedding_model_version=self.provider.model_version,
                        embedding_dimension=len(vec),
                        content_hash=c_hash,
                        created_at=now,
                        updated_at=now,
                    )
                    s.add(orm_emb)
                    total_indexed += 1

                await s.commit()

            logger.info(f"Successfully indexed {total_indexed} provision embeddings.")
            return total_indexed

        if session is not None:
            return await _run(session)
        else:
            async with get_async_session() as s:
                return await _run(s)

    async def search_similar(
        self,
        query_vector: list[float],
        top_k: int = 30,
        session: AsyncSession | None = None,
    ) -> list[tuple[str, float]]:
        """Retrieve nearest provisions using PostgreSQL pgvector cosine distance.
        
        Returns list of (provision_id, cosine_similarity_score [0, 1]).
        """
        async def _run(s: AsyncSession) -> list[tuple[str, float]]:
            if len(query_vector) != self.provider.dimension:
                raise ValueError(
                    f"Query embedding has dimension {len(query_vector)}; expected {self.provider.dimension}."
                )
            distance = KnowledgeProvisionEmbeddingORM.embedding.cosine_distance(query_vector)
            stmt = (
                select(KnowledgeProvisionEmbeddingORM.provision_id, distance.label("cosine_distance"))
                .where(
                    KnowledgeProvisionEmbeddingORM.embedding_model_id == self.provider.model_id,
                    KnowledgeProvisionEmbeddingORM.embedding_model_version == self.provider.model_version,
                )
                .order_by(distance)
                .limit(top_k)
            )
            rows = (await s.execute(stmt)).all()
            return [
                (provision_id, max(0.0, min(1.0, 1.0 - float(cosine_distance) / 2.0)))
                for provision_id, cosine_distance in rows
            ]

        if session is not None:
            return await _run(session)
        else:
            async with get_async_session() as s:
                return await _run(s)
