"""Lexical / BM25-style Full-Text Retrieval over SANGYAN Knowledge Provisions.

Epistemic foundation:
- Native PostgreSQL tsvector / GIN index execution.
- Considers provision text, title, section/clause references, authority, organisation, and process.
- ts_rank_cd covers term proximity and density.
- Scores normalized to [0.0, 1.0].
- In-memory fallback enables isolated offline testing.
"""

import logging
import re
from typing import Sequence
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ai.app.db.models import KnowledgeProvisionORM
from ai.app.db.session import get_async_session
from ai.app.knowledge.provisions import Provision
from ai.app.retrieval.contracts import RetrievalCandidate, RetrievalQuery

logger = logging.getLogger("sangyan.retrieval.lexical")


def sanitize_tsquery_terms(query_str: str) -> str:
    """Extract alphanumeric terms and format as boolean OR/AND tsquery string."""
    tokens = re.findall(r"\b[A-Za-z0-9_\-\/]+\b", query_str)
    # Filter very short noise tokens
    valid_tokens = [t for t in tokens if len(t) > 1 and not t.isdigit()]
    if not valid_tokens:
        return ""
    # Combine with '|' (OR) for broad recall
    return " | ".join(valid_tokens[:15])


class LexicalRetriever:
    """PostgreSQL native tsvector lexical retrieval engine."""

    async def retrieve(
        self,
        query: RetrievalQuery,
        limit: int = 30,
        session: AsyncSession | None = None,
        in_memory_provisions: Sequence[Provision] | None = None,
    ) -> list[tuple[str, float]]:
        """Retrieve candidates lexically. Returns list of (provision_id, lexical_score)."""
        # Formulate search string from query attributes
        search_terms: list[str] = []
        if query.query_text:
            search_terms.append(query.query_text)
        if query.issue:
            search_terms.append(query.issue)
        if query.disputed_action:
            search_terms.append(query.disputed_action)
        if query.instrument_or_service:
            search_terms.append(query.instrument_or_service)
        if query.key_terms:
            search_terms.extend(query.key_terms)

        raw_query = " ".join(search_terms).strip()
        if not raw_query:
            return []

        # If in-memory fallback is active
        if in_memory_provisions is not None:
            return self._retrieve_in_memory(raw_query, in_memory_provisions, limit)

        async def _run(s: AsyncSession) -> list[tuple[str, float]]:
            clean_terms = sanitize_tsquery_terms(raw_query)
            if not clean_terms:
                return []

            try:
                # Use plainto_tsquery and websearch_to_tsquery or to_tsquery
                query_sql = text("""
                    SELECT 
                        provision_id,
                        ts_rank_cd(search_vector, to_tsquery('english', :ts_query)) AS rank_score
                    FROM knowledge_provisions
                    WHERE search_vector @@ to_tsquery('english', :ts_query)
                    ORDER BY rank_score DESC
                    LIMIT :limit;
                """)
                res = await s.execute(query_sql, {"ts_query": clean_terms, "limit": limit})
                rows = res.fetchall()

                if not rows:
                    # Fallback to plainto_tsquery
                    query_sql_plain = text("""
                        SELECT 
                            provision_id,
                            ts_rank_cd(search_vector, plainto_tsquery('english', :raw_query)) AS rank_score
                        FROM knowledge_provisions
                        WHERE search_vector @@ plainto_tsquery('english', :raw_query)
                        ORDER BY rank_score DESC
                        LIMIT :limit;
                    """)
                    res2 = await s.execute(query_sql_plain, {"raw_query": raw_query, "limit": limit})
                    rows = res2.fetchall()

                if not rows:
                    return []

                # Normalize scores between 0.0 and 1.0
                max_score = max(r[1] for r in rows) if rows else 1.0
                if max_score <= 0.0:
                    max_score = 1.0

                return [(r[0], min(1.0, float(r[1]) / max_score)) for r in rows]

            except Exception as e:
                logger.warning(f"PostgreSQL tsvector query error: {e}. Falling back to ILIKE substring matching.")
                return await self._fallback_ilike(s, raw_query, limit)

        if session is not None:
            return await _run(session)
        else:
            try:
                async with get_async_session() as s:
                    return await _run(s)
            except Exception as e:
                logger.error(f"Failed to acquire db session for lexical retrieval: {e}")
                return []

    async def _fallback_ilike(
        self,
        session: AsyncSession,
        query_text: str,
        limit: int,
    ) -> list[tuple[str, float]]:
        """Fallback when tsquery has complex operators or syntax."""
        words = [w for w in re.findall(r"\w+", query_text) if len(w) > 2][:5]
        if not words:
            return []

        conditions = " OR ".join([f"source_text ILIKE :w_{i} OR title ILIKE :w_{i}" for i, _ in enumerate(words)])
        params = {f"w_{i}": f"%{w}%" for i, w in enumerate(words)}
        params["limit"] = limit

        sql = text(f"""
            SELECT provision_id
            FROM knowledge_provisions
            WHERE {conditions}
            LIMIT :limit;
        """)
        res = await session.execute(sql, params)
        rows = res.fetchall()
        return [(r[0], 0.5) for r in rows]

    def _retrieve_in_memory(
        self,
        raw_query: str,
        provisions: Sequence[Provision],
        limit: int,
    ) -> list[tuple[str, float]]:
        """Keyword matching for offline unit testing."""
        terms = [t.lower() for t in re.findall(r"\b[A-Za-z0-9_\-\/]+\b", raw_query) if len(t) > 1]
        if not terms:
            return []

        scored: list[tuple[str, float]] = []
        for p in provisions:
            text_target = f"{p.title or ''} {p.source_text} {p.section_reference or ''} {p.authority or ''} {p.organisation_id or ''}".lower()
            matches = sum(1 for t in terms if t in text_target)
            if matches > 0:
                score = matches / len(terms)
                scored.append((p.provision_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]
