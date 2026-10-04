"""Deterministic Multi-Factor Reranker and Epistemic Deduplication.

Epistemic foundation:
- Purely deterministic; NO LLM reranker.
- Deduplication preserves distinct legal layers (SEBI vs CDSL vs Intermediary).
- Multi-factor ranking:
  1. Exact Citation Matches
  2. Temporal Applicability (APPLICABLE > TEMPORALITY_UNRESOLVED > NOT_APPLICABLE)
  3. Hybrid Relevance Score
  4. Channel Agreement (candidates found by multiple retrieval methods get higher confidence)
  5. Authority Relevance
"""

import hashlib
import logging
from typing import Sequence

from ai.app.retrieval.contracts import RetrievalCandidate, RetrievalResult

logger = logging.getLogger("sangyan.retrieval.reranker")


def content_fingerprint(text: str) -> str:
    """Normalized content fingerprint for deduplication."""
    clean = "".join(text.lower().split())
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


class DeterministicReranker:
    """Reranks candidate provisions deterministically."""

    def deduplicate(
        self,
        candidates: Sequence[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        """Deduplicate identical source statements within the SAME authority or organisation.
        
        Crucially preserves identical or similar texts across DIFFERENT authorities (e.g. SEBI vs CDSL vs Zerodha).
        """
        seen_keys: set[str] = set()
        deduped: list[RetrievalCandidate] = []

        for c in candidates:
            owner = c.authority or c.organisation_id or "UNKNOWN"
            fp = content_fingerprint(c.source_text)
            dedup_key = f"{owner}:{fp}"

            if dedup_key in seen_keys:
                continue

            seen_keys.add(dedup_key)
            deduped.append(c)

        return deduped

    def rerank(
        self,
        candidates: list[RetrievalCandidate],
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        """Multi-factor sort and convert to RetrievalResult."""
        # Sorting key:
        # 1. Exact citation match (1 if c.citation_score > 0.8 else 0)
        # 2. Applicability rank (APPLICABLE: 2, TEMPORALITY_UNRESOLVED: 1, NOT_APPLICABLE: 0)
        # 3. Multi-channel agreement bonus (len(retrieval_methods))
        # 4. Hybrid score
        # 5. Authority score

        def sort_key(c: RetrievalCandidate) -> tuple:
            is_citation = 1 if c.citation_score > 0.8 else 0
            app_rank = 2 if c.applicability_status == "APPLICABLE" else (1 if c.applicability_status == "TEMPORALITY_UNRESOLVED" else 0)
            agreement = len(set(c.retrieval_methods))
            return (
                is_citation,
                app_rank,
                round(c.hybrid_score, 4),
                agreement,
                round(c.authority_score, 4),
            )

        ranked = sorted(candidates, key=sort_key, reverse=True)

        results: list[RetrievalResult] = []
        for rank, c in enumerate(ranked[:top_k], start=1):
            c.rank = rank
            results.append(
                RetrievalResult(
                    provision_id=c.provision_id,
                    rank=rank,
                    relevance_score=round(c.hybrid_score, 4),
                    lexical_score=round(c.lexical_score, 4),
                    semantic_score=round(c.semantic_score, 4),
                    citation_score=round(c.citation_score, 4) if c.citation_score > 0 else None,
                    metadata_score=round(c.metadata_score, 4),
                    authority_score=round(c.authority_score, 4),
                    temporal_status=c.temporal_status.value if hasattr(c.temporal_status, "value") else str(c.temporal_status),
                    applicability_status=c.applicability_status,
                    retrieval_methods=list(set(c.retrieval_methods)),
                    provision_type=c.provision_type.value if hasattr(c.provision_type, "value") else str(c.provision_type),
                    provision_text=c.source_text,
                    title=c.title,
                    section_reference=c.section_reference,
                    clause_reference=c.clause_reference,
                    authority=c.authority,
                    organisation_id=c.organisation_id,
                    source_class=c.source_class.value if hasattr(c.source_class, "value") else str(c.source_class),
                    document_id=c.document_id,
                    section_id=c.section_id,
                    citation=c.citation,
                    provenance=c.provenance,
                    source_url=c.source_url,
                )
            )

        return results
