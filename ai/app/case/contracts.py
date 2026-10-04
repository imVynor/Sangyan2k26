"""Case State Contracts, Event Model, and Versioning for SANGYAN.

Epistemic foundation:
- One case. One persistent state. Multiple contextual views over time.
- Immutable event-based append-only history. Never overwrite past evidence.
- Optimistic versioning with strict conflict detection: CASE_VERSION_CONFLICT.
- Retains contradictions rather than silently dropping conflicting claims.
- Stores auditable AssessmentSnapshots and AssessmentDeltas.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Sequence
import uuid
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import (
    AssessmentFinding,
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceRequirement,
    EvidenceType,
)
from ai.app.retrieval.contracts import RetrievalResponse


class CaseStatus(str, Enum):
    """Lifecycle status of a grievance case."""
    OPEN = "OPEN"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    EVALUATING = "EVALUATING"
    RESOLVED = "RESOLVED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REGULATORY_COVERAGE_UNRESOLVED = "REGULATORY_COVERAGE_UNRESOLVED"
    TEMPORALITY_UNRESOLVED = "TEMPORALITY_UNRESOLVED"
    CLOSED = "CLOSED"


class CaseEventType(str, Enum):
    """Controlled vocabulary of immutable case events."""
    CASE_CREATED = "CASE_CREATED"
    USER_MESSAGE_RECEIVED = "USER_MESSAGE_RECEIVED"
    DOCUMENT_ATTACHED = "DOCUMENT_ATTACHED"
    FACT_EXTRACTED = "FACT_EXTRACTED"
    EVIDENCE_ACCEPTED = "EVIDENCE_ACCEPTED"
    EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
    EVIDENCE_CONTRADICTION_DETECTED = "EVIDENCE_CONTRADICTION_DETECTED"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    CLARIFICATION_ANSWERED = "CLARIFICATION_ANSWERED"
    USER_DECLINED_EVIDENCE = "USER_DECLINED_EVIDENCE"
    RETRIEVAL_EXECUTED = "RETRIEVAL_EXECUTED"
    ASSESSMENT_EXECUTED = "ASSESSMENT_EXECUTED"
    ASSESSMENT_UPDATED = "ASSESSMENT_UPDATED"
    CASE_RESOLVED = "CASE_RESOLVED"


class CaseVersionConflictError(Exception):
    """Raised when an update targets a stale case version."""
    def __init__(self, message: str = "Case version conflict", expected_version: int | None = None, actual_version: int | None = None):
        super().__init__(message)
        self.expected_version = expected_version
        self.actual_version = actual_version


class CaseEvent(BaseModel):
    """Immutable, append-only event recorded in the case lifecycle."""
    event_id: str = Field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:12].upper()}")
    case_id: str
    case_version: int
    event_type: CaseEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="SYSTEM", description="USER, SYSTEM, ASSESSMENT_ENGINE, INVESTOR")
    source: str = Field(default="web", description="Origin channel or file name")
    idempotency_key: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssessmentSnapshot(BaseModel):
    """Point-in-time snapshot of an epistemic assessment."""
    snapshot_id: str = Field(default_factory=lambda: f"SNAP-{uuid.uuid4().hex[:12].upper()}")
    case_id: str
    case_version: int
    assessment_result: AssessmentResult
    trigger_event_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssessmentDelta(BaseModel):
    """Audit delta comparing previous assessment to the newly computed assessment."""
    case_id: str
    previous_status: AssessmentStatus | None = None
    new_status: AssessmentStatus
    status_changed: bool = False
    changed_findings: list[str] = Field(default_factory=list)
    new_evidence_ids: list[str] = Field(default_factory=list)
    newly_applicable_provisions: list[str] = Field(default_factory=list)
    newly_inapplicable_provisions: list[str] = Field(default_factory=list)
    resolved_uncertainties: list[str] = Field(default_factory=list)
    remaining_uncertainties: list[str] = Field(default_factory=list)
    rationale: str = ""


class CaseState(BaseModel):
    """Canonical persistent state of a grievance case."""
    case_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: CaseStatus = CaseStatus.OPEN
    version: int = 1

    # Confirmed empirical facts (e.g. {"charged_amount": Decimal("15.93"), "transaction_type": "equity_delivery"})
    facts: dict[str, Any] = Field(default_factory=dict)

    # Full audit list of all evidence items submitted across all turns
    evidence: list[EvidenceItem] = Field(default_factory=list)

    # Plausible hypotheses or working theories
    hypotheses: list[str] = Field(default_factory=list)

    # Fields explicitly declined by the user (do not re-ask)
    declined_fields: list[str] = Field(default_factory=list)

    # Active clarification questions awaiting citizen response
    unresolved_questions: list[dict[str, Any]] = Field(default_factory=list)

    # Current evidentiary requirements from assessment
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)

    # Number of clarification rounds conducted
    clarification_rounds: int = 0

    # Current retrieval state
    retrieval_state: RetrievalResponse | None = None

    # Assessment history snapshots
    assessment_history: list[AssessmentSnapshot] = Field(default_factory=list)

    # Current active assessment
    current_assessment: AssessmentResult | None = None

    # Latest delta from previous assessment
    latest_delta: AssessmentDelta | None = None

    # Append-only interaction events
    interaction_history: list[CaseEvent] = Field(default_factory=list)
