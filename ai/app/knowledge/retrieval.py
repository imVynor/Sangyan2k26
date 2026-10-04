"""Structured regulatory retrieval engine for SANGYAN.

Architecture:
CASE → ISSUE DOMAINS → AUTHORITY ROUTING → TEMPORAL FILTER → PARALLEL RETRIEVAL → AUTHORITY SORT

Epistemic foundation:
- Never return an anonymous chunk.
- Lowest-level organisation FAQ must never override statutory SEBI regulation.
- Secondary sources are ranked strictly below official regulatory and organisation policies.
- Evaluates temporal applicability (CURRENT_RULES vs HISTORICAL_RULES) strictly against incident dates.
"""

from datetime import date
from enum import Enum
from typing import Any, Sequence
from pydantic import BaseModel, Field

from ai.app.knowledge.documents import OrganisationDocument, RegulatoryDocument
from ai.app.knowledge.relationships import KnowledgeRelationship
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import TemporalResolutionState, TemporalScope
from ai.app.knowledge.temporal_engine import TemporalApplicabilityEngine
from ai.app.sources.routing import DomainRouter, KnowledgeDomain, RoutingTarget


class RetrievalMode(str, Enum):
    """Retrieval temporal strategy."""
    CURRENT_RULES = "CURRENT_RULES"
    HISTORICAL_RULES = "HISTORICAL_RULES"
    MULTI_AUTHORITY = "MULTI_AUTHORITY"


class RegulatoryRetrievalResult(BaseModel):
    """Contract for every regulatory retrieval result in SANGYAN."""
    document_id: str
    provision_id: str | None = None
    source_class: SourceClass
    authority: str | None = None
    organisation_id: str | None = None
    title: str
    section: str | None = None
    source_url: str
    source_hash: str
    publication_date: date | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    temporal_resolution: TemporalResolutionState
    authority_validation: str = "VALIDATED_AUTHORITY"
    citation: str
    relevance_score: float = 1.0
    retrieval_method: str = "structured_metadata"


SOURCE_CLASS_HIERARCHY_RANK: dict[SourceClass, int] = {
    SourceClass.REGULATORY: 1,
    SourceClass.ORGANISATION_POLICY: 2,
    SourceClass.ORGANISATION_PROCEDURE: 3,
    SourceClass.ORGANISATION_FAQ: 4,
    SourceClass.SECONDARY_SOURCE: 5,
}


class RetrievalQuery(BaseModel):
    """Specification of an incoming case retrieval request."""
    query_text: str | None = None
    mode: RetrievalMode = RetrievalMode.CURRENT_RULES
    incident_date: date | None = None
    reference_date: date | None = None
    organisation_id: str | None = None
    issue_domains: list[KnowledgeDomain] = Field(default_factory=list)
    target_authorities: list[str] = Field(default_factory=list)


class KnowledgeRetrievalEngine:
    """Orchestrates deterministic retrieval over structured knowledge repositories."""

    def __init__(
        self,
        router: DomainRouter | None = None,
        temporal_engine: TemporalApplicabilityEngine | None = None,
    ) -> None:
        self.router = router or DomainRouter()
        self.temporal_engine = temporal_engine or TemporalApplicabilityEngine()

    def determine_authorities_for_case(
        self,
        domains: list[KnowledgeDomain],
        organisation_id: str | None = None,
    ) -> list[str]:
        """Multi-authority candidate resolution from case understanding."""
        target = self.router.route_case(domains=domains, organisation_id=organisation_id)
        return target.authorities

    def evaluate_and_rank_results(
        self,
        documents: Sequence[RegulatoryDocument | OrganisationDocument],
        query: RetrievalQuery,
        relationships: Sequence[KnowledgeRelationship] | None = None,
    ) -> list[RegulatoryRetrievalResult]:
        """Filter by temporal applicability and rank strictly by source hierarchy."""
        eval_date = query.incident_date if query.mode == RetrievalMode.HISTORICAL_RULES else (query.reference_date or date.today())
        results: list[RegulatoryRetrievalResult] = []

        for doc in documents:
            scope = TemporalScope(
                publication_date=doc.publication_date,
                effective_date=doc.effective_date,
                termination_date=doc.termination_date,
                superseded_status=doc.superseded_status,
            )

            # Evaluate applicability against reference date
            if eval_date:
                temp_status = self.temporal_engine.evaluate_applicability(scope, eval_date, relationships)
            else:
                temp_status = TemporalResolutionState.TEMPORALITY_UNRESOLVED

            # Filter out documents not applicable to this regime
            if temp_status not in {TemporalResolutionState.APPLICABLE, TemporalResolutionState.TEMPORALITY_UNRESOLVED}:
                continue

            auth = getattr(doc, "authority", None)
            org_id = getattr(doc, "organisation_id", None)
            sec_str = getattr(doc, "section", None) or "General"

            # Formulate grounded legal citation
            owner_label = auth or org_id or "Regulatory Source"
            eff_str = f"effective from {doc.effective_date}" if doc.effective_date else "effective date unresolved"
            citation = f"{owner_label} — {doc.title} — Section {sec_str} — {eff_str}"

            results.append(
                RegulatoryRetrievalResult(
                    document_id=doc.document_id,
                    source_class=doc.source_class,
                    authority=auth,
                    organisation_id=org_id,
                    title=doc.title,
                    section=sec_str,
                    source_url=str(doc.source_url),
                    source_hash=doc.source_hash,
                    publication_date=doc.publication_date,
                    effective_date=doc.effective_date,
                    termination_date=doc.termination_date,
                    temporal_resolution=temp_status,
                    authority_validation="VALIDATED_AUTHORITY",
                    citation=citation,
                    relevance_score=1.0,
                    retrieval_method="structured_authority_route",
                )
            )

        # Sort by authoritative hierarchy rank (REGULATORY first, then POLICY, then PROCEDURE, etc.)
        results.sort(
            key=lambda r: (
                SOURCE_CLASS_HIERARCHY_RANK.get(r.source_class, 99),
                r.effective_date or date.min,
            ),
            reverse=False,
        )

        return results
