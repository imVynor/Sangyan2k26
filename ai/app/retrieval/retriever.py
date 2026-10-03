"""Provision-Level Hybrid Retriever Orchestrator for SANGYAN.

Epistemic foundation:
- Orchestrates multi-channel candidate retrieval: Lexical (tsvector), Semantic Vector (pgvector embeddings), Exact Citation, and Metadata.
- Fuses candidates with deterministic hybrid scoring, deduplication, and multi-factor reranking.
- Directly operates at Provision level, preserving complete provenance and citations.
- Explicitly flags failure states (NO_RELEVANT_PROVISIONS, TEMPORALITY_UNRESOLVED, REGULATORY_COVERAGE_UNRESOLVED).
"""

from datetime import date
import logging
import time
from typing import Protocol, Sequence, runtime_checkable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.app.db.mappers import knowledge_provision_from_orm
from ai.app.db.models import KnowledgeProvisionORM
from ai.app.db.session import get_async_session
from ai.app.knowledge.provisions import Provision
from ai.app.knowledge.temporal_engine import TemporalApplicabilityEngine
from ai.app.retrieval.citation import CitationRetriever
from ai.app.retrieval.contracts import (
    HybridRetrievalConfig,
    RetrievalCandidate,
    RetrievalFailureReason,
    RetrievalQuery,
    RetrievalResponse,
    RetrievalResult,
)
from ai.app.retrieval.embedding_provider import EmbeddingProvider
from ai.app.retrieval.embedding_store import ProvisionEmbeddingStore
from ai.app.retrieval.lexical import LexicalRetriever
from ai.app.retrieval.reranker import DeterministicReranker
from ai.app.retrieval.scoring import HybridScorer
from ai.app.retrieval.vector import VectorRetriever
from ai.app.sources.routing import DomainRouter, KnowledgeDomain

logger = logging.getLogger("sangyan.retrieval.retriever")


@runtime_checkable
class ProvisionRetriever(Protocol):
    """Protocol for provision retrieval services."""

    async def retrieve(
        self,
        query: RetrievalQuery,
        session: AsyncSession | None = None,
    ) -> RetrievalResponse:
        """Retrieve relevant provisions for a structured query."""
        ...


class DefaultProvisionRetriever:
    """Production implementation of ProvisionRetriever supporting PostgreSQL and in-memory execution."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        config: HybridRetrievalConfig | None = None,
        router: DomainRouter | None = None,
        temporal_engine: TemporalApplicabilityEngine | None = None,
        embedding_store: ProvisionEmbeddingStore | None = None,
    ) -> None:
        self.config = config or HybridRetrievalConfig()
        self.router = router or DomainRouter()
        self.temporal_engine = temporal_engine or TemporalApplicabilityEngine()
        self.embedding_provider = embedding_provider
        self.embedding_store = embedding_store or ProvisionEmbeddingStore(provider=embedding_provider)

        # Retrieval channels
        self.lexical_retriever = LexicalRetriever()
        self.vector_retriever = VectorRetriever(provider=embedding_provider, store=self.embedding_store)
        self.citation_retriever = CitationRetriever()
        self.scorer = HybridScorer(config=self.config, temporal_engine=self.temporal_engine)
        self.reranker = DeterministicReranker()

        # In-memory provision cache for offline test mode
        self._in_memory_provisions: list[Provision] = []

    def set_in_memory_provisions(self, provisions: Sequence[Provision]) -> None:
        """Configure retriever to run against an in-memory provision list for isolated unit tests."""
        self._in_memory_provisions = list(provisions)

    async def retrieve(
        self,
        query: RetrievalQuery,
        session: AsyncSession | None = None,
    ) -> RetrievalResponse:
        start_time = time.perf_counter()
        failure_reasons: list[RetrievalFailureReason] = []

        # 1. Authority & Domain Routing
        routing_target = self.router.route_case(
            domains=query.issue_domains,
            organisation_id=query.organisation_id,
        )
        routed_authorities = list(set(routing_target.authorities + query.target_authorities))
        routed_organisations = [query.organisation_id] if query.organisation_id else []

        if not routed_authorities and not routed_organisations:
            failure_reasons.append(RetrievalFailureReason.AUTHORITY_UNRESOLVED)

        # 2. Parallel Channel Retrieval
        in_mem = self._in_memory_provisions if self._in_memory_provisions else None

        # Channel A: Lexical / FTS
        lex_results = await self.lexical_retriever.retrieve(
            query=query,
            limit=self.config.candidate_lexical_limit,
            session=session,
            in_memory_provisions=in_mem,
        )

        # Channel B: Semantic Vector
        vec_results = await self.vector_retriever.retrieve(
            query=query,
            limit=self.config.candidate_vector_limit,
            session=session,
            in_memory_provisions=in_mem,
        )

        # Channel C: Exact Citation Lookup
        cit_results = await self.citation_retriever.retrieve(
            query=query,
            limit=self.config.candidate_citation_limit,
            session=session,
            in_memory_provisions=in_mem,
        )

        # 3. Merge Candidate Identifiers & Map Retrieval Methods
        candidate_ids: set[str] = set()
        methods_map: dict[str, set[str]] = {}
        scores_lex: dict[str, float] = {}
        scores_vec: dict[str, float] = {}
        scores_cit: dict[str, float] = {}

        for pid, score in lex_results:
            candidate_ids.add(pid)
            methods_map.setdefault(pid, set()).add("lexical")
            scores_lex[pid] = max(scores_lex.get(pid, 0.0), score)

        for pid, score in vec_results:
            candidate_ids.add(pid)
            methods_map.setdefault(pid, set()).add("vector")
            scores_vec[pid] = max(scores_vec.get(pid, 0.0), score)

        for pid, score in cit_results:
            candidate_ids.add(pid)
            methods_map.setdefault(pid, set()).add("exact_citation")
            scores_cit[pid] = max(scores_cit.get(pid, 0.0), score)

        if not candidate_ids:
            duration = time.perf_counter() - start_time
            failure_reasons.append(RetrievalFailureReason.NO_RELEVANT_PROVISIONS)
            return RetrievalResponse(
                results=[],
                failure_reasons=failure_reasons,
                total_candidates_found=0,
                routed_authorities=routed_authorities,
                routed_organisations=routed_organisations,
                retrieval_stats={"duration_ms": round(duration * 1000, 2), "channel_counts": {"lexical": 0, "vector": 0, "citation": 0}},
            )

        # 4. Fetch Full Provision Entities
        provisions_map: dict[str, Provision] = {}
        if in_mem is not None:
            provisions_map = {p.provision_id: p for p in in_mem if p.provision_id in candidate_ids}
        else:
            # Query from PostgreSQL
            async def _fetch_provisions(s: AsyncSession) -> dict[str, Provision]:
                stmt = select(KnowledgeProvisionORM).where(KnowledgeProvisionORM.provision_id.in_(list(candidate_ids)))
                res = await s.execute(stmt)
                orms = res.scalars().all()
                return {orm.provision_id: knowledge_provision_from_orm(orm) for orm in orms}

            if session is not None:
                provisions_map = await _fetch_provisions(session)
            else:
                try:
                    async with get_async_session() as s:
                        provisions_map = await _fetch_provisions(s)
                except Exception as e:
                    logger.error(f"Error fetching provisions: {e}")

        # 5. Build RetrievalCandidates with Provenance & Citations
        candidates: list[RetrievalCandidate] = []
        for pid in candidate_ids:
            prov = provisions_map.get(pid)
            if not prov:
                continue

            # Formulate grounded legal citation
            owner_label = prov.authority or prov.organisation_id or "Regulatory Source"
            sec_str = prov.section_reference or "General"
            eff_str = f"effective from {prov.effective_date}" if prov.effective_date else "effective date unresolved"
            citation = f"{owner_label} — {prov.title or prov.provision_type.value} — Section {sec_str} — {eff_str}"

            cand = RetrievalCandidate(
                provision_id=prov.provision_id,
                document_id=prov.document_id,
                section_id=prov.section_id,
                provision_type=prov.provision_type,
                source_text=prov.source_text,
                title=prov.title,
                section_reference=prov.section_reference,
                clause_reference=prov.clause_reference,
                authority=prov.authority,
                organisation_id=prov.organisation_id,
                source_class=prov.source_class,
                process=prov.process,
                effective_date=prov.effective_date,
                termination_date=prov.termination_date,
                provenance=prov.provenance,
                citation=citation,
                source_url=str(prov.provenance.source_url) if prov.provenance else "",
                retrieval_methods=list(methods_map.get(pid, set())),
                lexical_score=scores_lex.get(pid, 0.0),
                semantic_score=scores_vec.get(pid, 0.0),
                citation_score=scores_cit.get(pid, 0.0),
            )
            candidates.append(cand)

        # 6. Hybrid Scoring and Temporal Validation
        scored_candidates = self.scorer.score_and_validate(
            candidates=candidates,
            query=query,
            routed_authorities=routed_authorities,
            routed_organisations=routed_organisations,
        )

        # 7. Deduplication (preserving distinct authorities)
        deduped_candidates = self.reranker.deduplicate(scored_candidates)

        # Filter by minimum threshold
        filtered = [c for c in deduped_candidates if c.hybrid_score >= self.config.min_hybrid_threshold or c.citation_score > 0.8]

        # 8. Deterministic Multi-Factor Rerank
        final_results = self.reranker.rerank(filtered, top_k=query.top_k)

        # 9. Failure State Detection
        if not final_results:
            failure_reasons.append(RetrievalFailureReason.NO_RELEVANT_PROVISIONS)
        else:
            # Check if all results have unresolved temporality when an incident date was provided
            if query.incident_date and all(r.applicability_status == "TEMPORALITY_UNRESOLVED" for r in final_results):
                failure_reasons.append(RetrievalFailureReason.TEMPORALITY_UNRESOLVED)

        duration = time.perf_counter() - start_time
        return RetrievalResponse(
            results=final_results,
            failure_reasons=failure_reasons,
            total_candidates_found=len(candidate_ids),
            routed_authorities=routed_authorities,
            routed_organisations=routed_organisations,
            retrieval_stats={
                "duration_ms": round(duration * 1000, 2),
                "candidates_merged": len(candidate_ids),
                "channel_counts": {
                    "lexical": len(lex_results),
                    "vector": len(vec_results),
                    "citation": len(cit_results),
                },
            },
        )
