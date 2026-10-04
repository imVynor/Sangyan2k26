"""Orchestration Contracts, Turn Results, and Error Hierarchy for SANGYAN.

Epistemic foundation:
- Coordinates the complete turn lifecycle across extraction, evidence policy, retrieval,
  assessment, clarification, and generation.
- Generation is strictly downstream-only presentation: generation failure does not invalidate
  an epistemic assessment.
- Clear distinction between operational failures and epistemic uncertainty (EVIDENCE_INSUFFICIENT).
- Tracks structured ActionIntents (Action Executor is explicitly NOT_IMPLEMENTED).
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Sequence
import uuid
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import (
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    EvidenceItem,
    EvidenceType,
)
from ai.app.case.contracts import (
    AssessmentDelta,
    CaseEvent,
    CaseEventType,
    CaseState,
    CaseStatus,
)
from ai.app.clarification.contracts import ClarificationPlan
from ai.app.evidence_policy.contracts import Claim, ResolvedFieldClaim
from ai.app.extraction.document_extractor import DocumentExtractionPayload
from ai.app.generation.contracts import GeneratedResponse
from ai.app.retrieval.contracts import RetrievalResponse


# =====================================================================
# ACTION INTENTS (Boundary for Future Actions)
# =====================================================================

class ActionTarget(str, Enum):
    """Target actor or entity for an action intent."""
    USER = "USER"
    BROKER = "BROKER"
    REGULATOR = "REGULATOR"
    EXCHANGE = "EXCHANGE"
    DEPOSITORY = "DEPOSITORY"
    SYSTEM = "SYSTEM"


class ActionIntent(BaseModel):
    """Structured declaration of a future action (execution deferred)."""
    intent_id: str = Field(default_factory=lambda: f"ACT-{uuid.uuid4().hex[:8].upper()}")
    action_type: str = Field(description="e.g. REQUEST_DOCUMENT, NOTIFY_INVESTOR, PREPARE_REGULATORY_PETITION")
    target: ActionTarget = ActionTarget.USER
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    rationale: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =====================================================================
# GENERATION SNAPSHOT (Audit presentation metadata)
# =====================================================================

class GenerationSnapshot(BaseModel):
    """Provenance metadata for auditable generated presentation."""
    model_id: str = "mock-llm-deterministic"
    model_version: str = "v1.0.0"
    prompt_version: str = "sangyan-explainer-v2"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "COMPLETED"  # "COMPLETED" or "FAILED"
    error_message: str | None = None


# =====================================================================
# TURN INPUT & OUTPUT
# =====================================================================

class OrchestrationInputEvent(BaseModel):
    """Input payload triggering a case lifecycle turn."""
    event_type: CaseEventType = CaseEventType.USER_MESSAGE_RECEIVED
    complaint_text: str | None = None
    user_message: str | None = None
    documents: list[DocumentExtractionPayload] = Field(default_factory=list)
    declined_field: str | None = None
    reference_date: date | None = None
    language: str = "en"
    actor: str = "USER"
    source: str = "web"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseTurnResult(BaseModel):
    """Structured, auditable outcome of an orchestrated turn."""
    case_id: str
    turn_id: str = Field(default_factory=lambda: f"TRN-{uuid.uuid4().hex[:8].upper()}")
    previous_version: int
    new_version: int
    previous_status: CaseStatus
    new_status: CaseStatus
    status_transition: str
    accepted_evidence: list[EvidenceItem] = Field(default_factory=list)
    new_facts: dict[str, Any] = Field(default_factory=dict)
    claims: list[Claim] = Field(default_factory=list)
    resolved_claims: list[ResolvedFieldClaim] = Field(default_factory=list)
    retrieval_response: RetrievalResponse
    assessment_result: AssessmentResult
    assessment_delta: AssessmentDelta
    clarification_plan: ClarificationPlan
    generated_response: GeneratedResponse | None = None
    generation_snapshot: GenerationSnapshot | None = None
    action_intents: list[ActionIntent] = Field(default_factory=list)
    events_created: list[CaseEvent] = Field(default_factory=list)
    knowledge_snapshot_id: str = "KNOW-2026-V1"
    duration_ms: float = 0.0


# =====================================================================
# ERROR HIERARCHY & RETRY SEMANTICS
# =====================================================================

class OrchestrationError(Exception):
    """Base error for orchestrator failures."""
    def __init__(self, message: str, is_retryable: bool = False, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.is_retryable = is_retryable
        self.details = details or {}


class InvalidStateTransitionError(OrchestrationError):
    """Raised when an illegal case lifecycle state transition is attempted."""
    def __init__(self, from_status: str, to_status: str, reason: str = ""):
        super().__init__(
            f"INVALID_STATE_TRANSITION: Cannot transition from '{from_status}' to '{to_status}'. {reason}".strip(),
            is_retryable=False,
            details={"from_status": from_status, "to_status": to_status},
        )


class ExtractionError(OrchestrationError):
    """Raised when fact/evidence extraction fails."""
    def __init__(self, message: str, is_retryable: bool = True):
        super().__init__(f"EXTRACTION_FAILED: {message}", is_retryable=is_retryable)


class RetrievalError(OrchestrationError):
    """Raised when regulatory provision retrieval fails."""
    def __init__(self, message: str, is_retryable: bool = True):
        super().__init__(f"RETRIEVAL_FAILED: {message}", is_retryable=is_retryable)


class AssessmentError(OrchestrationError):
    """Raised when rule evaluation or epistemic assessment crashes unexpectedly."""
    def __init__(self, message: str, is_retryable: bool = False):
        super().__init__(f"ASSESSMENT_FAILED: {message}", is_retryable=is_retryable)


class GenerationError(OrchestrationError):
    """Raised when downstream presentation generation fails."""
    def __init__(self, message: str, is_retryable: bool = True):
        super().__init__(f"GENERATION_FAILED: {message}", is_retryable=is_retryable)


class DuplicateEventError(OrchestrationError):
    """Raised when an idempotency conflict occurs."""
    def __init__(self, idempotency_key: str):
        super().__init__(
            f"DUPLICATE_EVENT: Event with idempotency key '{idempotency_key}' already processed.",
            is_retryable=False,
            details={"idempotency_key": idempotency_key},
        )
