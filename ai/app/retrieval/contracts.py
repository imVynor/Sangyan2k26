"""Core contracts and data schemas for SANGYAN Hybrid Provision Retrieval.

Epistemic foundation:
- Retrieval unit is strictly Provision (never anonymous chunks).
- Distinguishes Relevance from Applicability (a provision can be highly relevant but temporally expired).
- Epistemically distinct authorities (SEBI, CDSL, Intermediary) are preserved during deduplication.
- Explicit failure states prevent downstream hallucinations.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Sequence
from pydantic import BaseModel, Field

from ai.app.knowledge.provisions import ProvisionType
from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import TemporalResolutionState
from ai.app.sources.routing import KnowledgeDomain


class RetrievalMode(str, Enum):
    """Retrieval temporal and scope strategy."""
    CURRENT_RULES = "CURRENT_RULES"
    HISTORICAL_RULES = "HISTORICAL_RULES"
    MULTI_AUTHORITY = "MULTI_AUTHORITY"


class RetrievalFailureReason(str, Enum):
    """Explicit retrieval failure modes."""
    NO_RELEVANT_PROVISIONS = "NO_RELEVANT_PROVISIONS"
    REGULATORY_COVERAGE_UNRESOLVED = "REGULATORY_COVERAGE_UNRESOLVED"
    TEMPORALITY_UNRESOLVED = "TEMPORALITY_UNRESOLVED"
    SOURCE_VALIDATION_FAILED = "SOURCE_VALIDATION_FAILED"
    AUTHORITY_UNRESOLVED = "AUTHORITY_UNRESOLVED"
    CORPUS_GAP = "CORPUS_GAP"


@dataclass
class HybridRetrievalConfig:
    """Configurable weights and thresholds for hybrid retrieval scoring."""
    w_lexical: float = 0.35
    w_semantic: float = 0.35
    w_citation: float = 0.20
    w_metadata: float = 0.10
    min_hybrid_threshold: float = 0.15
    candidate_lexical_limit: int = 30
    candidate_vector_limit: int = 30
    candidate_citation_limit: int = 10
    candidate_metadata_limit: int = 20
    default_top_k: int = 10


class RetrievalQuery(BaseModel):
    """Structured query representation derived from case understanding."""
    query_text: str | None = Field(default=None, description="Synthesized natural query representation.")
    issue: str | None = Field(default=None, description="Primary substantive legal/operational issue.")
    issue_category: str | None = Field(default=None, description="Category of the grievance.")
    disputed_action: str | None = Field(default=None, description="Action or omission being disputed.")
    actor: str | None = Field(default=None, description="Entity who performed the action.")
    organisation_id: str | None = Field(default=None, description="Target market intermediary (e.g. ORG_ZERODHA).")
    instrument_or_service: str | None = Field(default=None, description="Financial instrument or service involved.")
    mode: RetrievalMode = Field(default=RetrievalMode.CURRENT_RULES)
    incident_date: date | None = Field(default=None, description="Date the disputed event occurred.")
    reference_date: date | None = Field(default=None, description="Target evaluation date (defaults to today).")
    issue_domains: list[KnowledgeDomain] = Field(default_factory=list, description="Categorical grievance domains.")
    target_authorities: list[str] = Field(default_factory=list, description="Authorities explicitly targeted.")
    target_citations: list[str] = Field(default_factory=list, description="Explicit circular, regulation, or section citations.")
    key_terms: list[str] = Field(default_factory=list, description="High-diagnostic domain terms.")
    top_k: int = Field(default=10, description="Maximum number of final results to return.")


class RetrievalCandidate(BaseModel):
    """Internal candidate representation retrieved from one or more channels."""
    provision_id: str
    document_id: str
    section_id: str | None = None
    provision_type: ProvisionType
    source_text: str
    title: str | None = None
    section_reference: str | None = None
    clause_reference: str | None = None
    authority: str | None = None
    organisation_id: str | None = None
    source_class: SourceClass
    process: str | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    temporal_status: TemporalResolutionState = TemporalResolutionState.TEMPORALITY_UNRESOLVED
    applicability_status: str = "TEMPORALITY_UNRESOLVED"  # APPLICABLE, NOT_APPLICABLE, TEMPORALITY_UNRESOLVED
    provenance: Provenance | None = None
    citation: str = ""
    source_url: str = ""
    retrieval_methods: list[str] = Field(default_factory=list)  # ["lexical", "vector", "exact_citation", "metadata"]

    # Component scores (normalized [0, 1])
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    citation_score: float = 0.0
    metadata_score: float = 0.0
    authority_score: float = 0.0
    hybrid_score: float = 0.0
    rank: int = 0


class RetrievalResult(BaseModel):
    """Public contract for every retrieved provision result."""
    provision_id: str
    rank: int
    relevance_score: float = Field(description="Combined hybrid relevance score [0, 1].")
    lexical_score: float | None = None
    semantic_score: float | None = None
    citation_score: float | None = None
    metadata_score: float | None = None
    authority_score: float | None = None

    temporal_status: str = Field(description="Temporal resolution state (e.g. APPLICABLE, SUPERSEDED).")
    applicability_status: str = Field(description="Legal applicability: APPLICABLE, NOT_APPLICABLE, TEMPORALITY_UNRESOLVED.")

    retrieval_methods: list[str] = Field(default_factory=list)
    provision_type: str
    provision_text: str
    title: str | None = None
    section_reference: str | None = None
    clause_reference: str | None = None

    authority: str | None = None
    organisation_id: str | None = None
    source_class: str

    document_id: str
    section_id: str | None = None

    citation: str
    provenance: Provenance | None = None
    source_url: str
    effective_from: date | None = None
    effective_to: date | None = None


class RetrievalResponse(BaseModel):
    """Complete envelope returned by ProvisionRetriever."""
    results: list[RetrievalResult] = Field(default_factory=list)
    failure_reasons: list[RetrievalFailureReason] = Field(default_factory=list)
    total_candidates_found: int = 0
    routed_authorities: list[str] = Field(default_factory=list)
    routed_organisations: list[str] = Field(default_factory=list)
    retrieval_stats: dict[str, Any] = Field(default_factory=dict)
