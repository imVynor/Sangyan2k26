"""Evidence Policy Contracts for SANGYAN.

Epistemic foundation:
- Evidence attaches to a Claim, not only an abstract field.
- Multiple claims for a field are preserved with full provenance.
- Field/claim-specific authority policies resolve operative values without erasing contradictions.
- Distinguishes evidence resolution ("What empirical value do we currently accept?")
  from legal assessment ("What does the applicable regulation imply given those facts?").
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Sequence
import uuid
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import EvidenceItem, EvidenceType


class EvidenceAuthorityScope(str, Enum):
    """Domain scope governed by an evidence policy."""
    FINANCIAL_TARIFF = "FINANCIAL_TARIFF"
    TEMPORAL_RECORD = "TEMPORAL_RECORD"
    TRADE_SPECIFICATION = "TRADE_SPECIFICATION"
    ACCOUNT_METADATA = "ACCOUNT_METADATA"
    SUBJECTIVE_EXPERIENCE = "SUBJECTIVE_EXPERIENCE"
    COMMUNICATION_HISTORY = "COMMUNICATION_HISTORY"
    SERVICE_OUTAGE = "SERVICE_OUTAGE"
    GENERAL = "GENERAL"


class ClaimStatus(str, Enum):
    """Lifecycle and reconciliation status of an empirical claim."""
    UNRESOLVED = "UNRESOLVED"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    RESOLVED_BY_POLICY = "RESOLVED_BY_POLICY"
    RESOLVED_BY_ADDITIONAL_EVIDENCE = "RESOLVED_BY_ADDITIONAL_EVIDENCE"


class Claim(BaseModel):
    """An explicit, provenance-backed claim submitted by an actor or document."""
    claim_id: str = Field(default_factory=lambda: f"CLM-{uuid.uuid4().hex[:8].upper()}")
    case_id: str | None = None
    field_name: str
    claim_text: str = ""
    claimed_value: Any
    source_type: EvidenceType = EvidenceType.USER_STATEMENT
    source_id: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.UNRESOLVED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceResolutionPolicy(BaseModel):
    """Configurable rule determining relative authority of evidence sources for a specific field."""
    policy_id: str
    field_name: str
    authority_scope: EvidenceAuthorityScope = EvidenceAuthorityScope.GENERAL
    precedence: list[EvidenceType] = Field(
        description="Ordered list of evidence types from highest authority to lowest authority."
    )
    tie_breaker: str = "CONTRADICTED"
    description: str = ""


class ResolvedFieldClaim(BaseModel):
    """Reconciled operative result for an empirical field across all its claims."""
    field_name: str
    operative_value: Any = None
    status: ClaimStatus
    active_claim_id: str | None = None
    supporting_claim_ids: list[str] = Field(default_factory=list)
    contradicting_claim_ids: list[str] = Field(default_factory=list)
    all_claims: list[Claim] = Field(default_factory=list)
    applied_policy_id: str | None = None
    resolution_rationale: str = ""
