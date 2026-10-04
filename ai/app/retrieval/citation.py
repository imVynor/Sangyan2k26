"""Exact Citation Retrieval for SANGYAN Provisions.

Epistemic foundation:
- Exact authoritative citations (circular numbers, regulation numbers, section/clause references)
  represent high-confidence legal truth and must not be suppressed by lower semantic similarity.
- Assigns deterministic citation confidence score (1.0).
"""

import logging
import re
from typing import Sequence
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ai.app.db.models import KnowledgeProvisionORM
from ai.app.db.session import get_async_session
from ai.app.knowledge.provisions import Provision
from ai.app.retrieval.contracts import RetrievalQuery

logger = logging.getLogger("sangyan.retrieval.citation")

# Regulatory citation patterns
CIRCULAR_REGEX = re.compile(r"SEBI\/[A-Z0-9_\-\/]+|CIR\/[A-Z0-9_\-\/]+", re.IGNORECASE)
REGULATION_REGEX = re.compile(r"(?:regulation|reg\.?|clause|section|rule)\s*(\d+[A-Za-z0-9\(\)\.\-]*)", re.IGNORECASE)


class CitationRetriever:
    """Exact citation matcher for statutory and regulatory provisions."""

    async def retrieve(
        self,
        query: RetrievalQuery,
        limit: int = 10,
        session: AsyncSession | None = None,
        in_memory_provisions: Sequence[Provision] | None = None,
    ) -> list[tuple[str, float]]:
        """Retrieve provisions matching explicit citation targets.
        
        Returns list of (provision_id, citation_score).
        """
        targets: set[str] = set()

        # 1. From explicit query target citations
        for c in query.target_citations:
            targets.add(c.strip())

        # 2. Extract circular patterns from query text and issue
        combined_text = f"{query.query_text or ''} {query.issue or ''}"
        for match in CIRCULAR_REGEX.finditer(combined_text):
            targets.add(match.group(0).strip())

        # 3. Extract regulation / clause references
        for match in REGULATION_REGEX.finditer(combined_text):
            targets.add(match.group(0).strip())
            # Also add bare number
            targets.add(match.group(1).strip())

        if not targets:
            return []

        # If in-memory provisions provided
        if in_memory_provisions is not None:
            return self._retrieve_in_memory(targets, in_memory_provisions, limit)

        async def _run(s: AsyncSession) -> list[tuple[str, float]]:
            matched_ids: set[str] = set()
            for t in targets:
                pattern = f"%{t}%"
                stmt = select(KnowledgeProvisionORM.provision_id).where(
                    or_(
                        KnowledgeProvisionORM.section_reference.ilike(pattern),
                        KnowledgeProvisionORM.clause_reference.ilike(pattern),
                        KnowledgeProvisionORM.title.ilike(pattern),
                        KnowledgeProvisionORM.source_text.ilike(pattern),
                        KnowledgeProvisionORM.provision_id == t,
                    )
                ).limit(limit)
                rows = (await s.execute(stmt)).fetchall()
                for r in rows:
                    matched_ids.add(r[0])

            # Exact citations get top confidence score (1.0)
            return [(pid, 1.0) for pid in list(matched_ids)[:limit]]

        if session is not None:
            return await _run(session)
        else:
            try:
                async with get_async_session() as s:
                    return await _run(s)
            except Exception as e:
                logger.error(f"Error executing citation retrieval: {e}")
                return []

    def _retrieve_in_memory(
        self,
        targets: set[str],
        provisions: Sequence[Provision],
        limit: int,
    ) -> list[tuple[str, float]]:
        matched: set[str] = set()
        for t in targets:
            t_lower = t.lower()
            for p in provisions:
                ref = (p.section_reference or "").lower()
                clause = (p.clause_reference or "").lower()
                title = (p.title or "").lower()
                src = p.source_text.lower()
                if (
                    t_lower in ref
                    or t_lower in clause
                    or t_lower in title
                    or t_lower in src
                    or p.provision_id == t
                ):
                    matched.add(p.provision_id)

        return [(pid, 1.0) for pid in list(matched)[:limit]]
