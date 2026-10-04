"""Source validation and deterministic resolution contracts for SANGYAN.

Epistemic foundation:
The LLM must NOT own citation validity, source truth, or temporal applicability.
These contracts define the deterministic services that will resolve:
1. Source verification (SourceValidator)
2. Citation -> Document -> Provision (CitationResolver)
3. Document candidates + Incident date -> Applicable version (VersionResolver)
4. Temporal and scope applicability (ApplicabilityResolver)
"""

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, HttpUrl

from ai.app.knowledge.documents import OrganisationDocument, RegulatoryDocument
from ai.app.knowledge.provisions import RegulatoryProvision
from ai.app.knowledge.temporal import TemporalResolutionState


# =====================================================================
# 1. Source Validator Contract
# =====================================================================

class SourceValidationRequest(BaseModel):
    """Input payload to verify document source authenticity and hash integrity."""
    source_url: HttpUrl
    source_hash: str
    document_id: str
    expected_source_class: str


class SourceValidationResult(BaseModel):
    """Result of deterministic source verification."""
    is_valid: bool
    document_id: str
    errors: list[str] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceValidator(ABC):
    """Abstract contract for validating document provenance and source authenticity."""

    @abstractmethod
    async def validate_source(self, request: SourceValidationRequest) -> SourceValidationResult:
        """Verify that source URL and cryptographic hash are genuine and untampered."""
        ...


# =====================================================================
# 2. Citation Resolver Contract
# =====================================================================

class CitationResolutionRequest(BaseModel):
    """Input citation query (e.g. 'SEBI Circular CIR/MRD/DP/54/2017 Clause 3')."""
    citation_text: str = Field(min_length=1)
    authority_hint: str | None = None
    jurisdiction: str = "India"


class CitationResolutionResult(BaseModel):
    """Resolved document and provision targets."""
    resolved: bool
    citation_text: str
    document_id: str | None = None
    provision_id: str | None = None
    resolution_notes: str | None = None


class CitationResolver(ABC):
    """Abstract contract resolving: citation -> document -> provision."""

    @abstractmethod
    async def resolve_citation(self, request: CitationResolutionRequest) -> CitationResolutionResult:
        """Deterministically link a raw citation string to an ingested document and provision."""
        ...


# =====================================================================
# 3. Version Resolver Contract
# =====================================================================

class VersionResolutionRequest(BaseModel):
    """Input candidates and incident date for version resolution."""
    document_identifier: str
    candidate_documents: list[RegulatoryDocument | OrganisationDocument]
    incident_date: date


class VersionResolutionResult(BaseModel):
    """Result determining operative document version or TEMPORALITY_UNRESOLVED."""
    applicable_document_id: str | None = None
    resolution_state: TemporalResolutionState
    incident_date: date
    notes: str | None = None


class VersionResolver(ABC):
    """Abstract contract resolving: document candidates + incident date -> applicable version."""

    @abstractmethod
    async def resolve_version(self, request: VersionResolutionRequest) -> VersionResolutionResult:
        """Determine which document version governed the market on the incident date."""
        ...


# =====================================================================
# 4. Applicability Resolver Contract
# =====================================================================

class ApplicabilityResolutionRequest(BaseModel):
    """Input criteria to check if a specific provision applies to a case scenario."""
    provision_id: str
    incident_date: date
    market_participant_type: str | None = None
    transaction_segment: str | None = None


class ApplicabilityResolutionResult(BaseModel):
    """Result confirming rule applicability."""
    is_applicable: bool
    state: TemporalResolutionState
    reason: str | None = None


class ApplicabilityResolver(ABC):
    """Abstract contract for determining if a provision governs an investor's specific scenario."""

    @abstractmethod
    async def resolve_applicability(
        self, request: ApplicabilityResolutionRequest
    ) -> ApplicabilityResolutionResult:
        ...


# =====================================================================
# 5. Case State vs Knowledge State Boundary Enforcement
# =====================================================================

class CaseKnowledgeBoundaryError(TypeError):
    """Raised when case state (Fact/Claim) is improperly passed where knowledge is required."""
    pass


def assert_not_case_state(obj: Any) -> None:
    """Enforce strict separation between Case state and Regulatory Knowledge state.
    
    A user narrative Fact or Claim must NEVER masquerade as a Regulatory Document or Provision.
    """
    type_name = type(obj).__name__
    if type_name in {"Fact", "Claim", "CaseUnderstanding", "Unknown", "Hypothesis"}:
        raise CaseKnowledgeBoundaryError(
            f"Epistemic Boundary Violation: Object of type '{type_name}' belongs to "
            f"Case State domain and CANNOT be stored or substituted as Regulatory Knowledge."
        )
