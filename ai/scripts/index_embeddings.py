"""Compute and persist dense embeddings for all provisions in PostgreSQL.

Uses OllamaEmbeddingProvider with nomic-embed-text (dimension 768).
Enforces content-hash caching so unchanged provisions are never re-embedded.
"""

import asyncio
import os
import sys
import time

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from ai.app.config.settings import settings
from ai.app.db.repository import PostgresKnowledgeRepository
from ai.app.db.session import get_async_session
from ai.app.retrieval.embedding_provider import OllamaEmbeddingProvider
from ai.app.retrieval.embedding_store import ProvisionEmbeddingStore


async def run_indexing() -> None:
    print("=" * 70)
    print("SANGYAN Provision Dense Embedding Indexer")
    print("=" * 70)

    db_url = settings.database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL is not set.")
        return

    provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url or "http://localhost:11434",
        model_id="nomic-embed-text",
        model_version="v1.5",
        dimension=768,
    )
    store = ProvisionEmbeddingStore(provider=provider)
    repo = PostgresKnowledgeRepository()

    repo = PostgresKnowledgeRepository()
    provisions = await repo.list_all_knowledge_provisions()
    print(f"[CORPUS] Found {len(provisions)} provisions in PostgreSQL.")

    start_time = time.perf_counter()
    async with get_async_session() as session:

        print(f"[EMBEDDING] Model: {provider.model_id} ({provider.model_version}), Dimension: {provider.dimension}")
        indexed = await store.index_provisions(provisions=provisions, session=session, batch_size=40)
        duration = time.perf_counter() - start_time
        print(f"[COMPLETE] Indexed {indexed} new provision embeddings in {duration:.2f}s.")


if __name__ == "__main__":
    asyncio.run(run_indexing())
