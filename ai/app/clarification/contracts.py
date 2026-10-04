"""Clarification Contracts and Schemas for SANGYAN Multi-Turn Dialogue.

Epistemic foundation:
- Clarification questions must be deterministically planned, not invented on a whim.
- Minimum necessary information burden: ask only what can change assessment state.
- Never re-ask known facts or previously declined questions.
- Retains language-independent field contracts with multilingual renderings.
"""

from enum import Enum
from typing import Any
import uuid
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import EvidenceType


class QuestionPriority(str, Enum):
    """Priority level based on potential assessment state transition."""
    CRITICAL = "CRITICAL"   # Resolves VIOLATION vs COMPLIANT or INSUFFICIENT vs DEFINITIVE
    HIGH = "HIGH"           # Substantially limits applicable circulars/provisions
    MEDIUM = "MEDIUM"       # Confirmatory documentary support
    LOW = "LOW"             # Ancillary procedural detail


class ClarificationPlanStatus(str, Enum):
    """Status of the clarification planning phase."""
    QUESTIONS_REQUIRED = "QUESTIONS_REQUIRED"
    RESOLVED = "RESOLVED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REGULATORY_COVERAGE_UNRESOLVED = "REGULATORY_COVERAGE_UNRESOLVED"
    TEMPORALITY_UNRESOLVED = "TEMPORALITY_UNRESOLVED"
    USER_DECLINED = "USER_DECLINED"
    MAX_CLARIFICATIONS_REACHED = "MAX_CLARIFICATIONS_REACHED"


class ClarificationQuestion(BaseModel):
    """Specification of a single targeted clarification question."""
    question_id: str = Field(default_factory=lambda: f"Q-{uuid.uuid4().hex[:8].upper()}")
    field: str = Field(description="Target canonical fact name (e.g. 'transaction_type', 'transaction_date').")
    question: str = Field(description="Human-readable citizen-facing question text in primary language.")
    reason: str = Field(description="Deterministic regulatory explanation for why this fact is needed.")
    required_for: list[str] = Field(default_factory=list, description="IDs of affected provisions or rules.")
    priority: QuestionPriority = Field(default=QuestionPriority.HIGH)
    expected_answer_type: str = Field(default="STRING", description="ENUM, DECIMAL, DATE, DOCUMENT, STRING, BOOLEAN")
    acceptable_values: list[str] | None = None
    acceptable_evidence_types: list[EvidenceType] = Field(
        default_factory=lambda: [EvidenceType.USER_STATEMENT, EvidenceType.DOCUMENT]
    )
    multilingual_text: dict[str, str] = Field(
        default_factory=dict,
        description="Localized renderings for 'en', 'hi', 'hinglish'."
    )


class ClarificationPlan(BaseModel):
    """Deterministic plan for the current dialogue turn."""
    plan_id: str = Field(default_factory=lambda: f"PLAN-{uuid.uuid4().hex[:8].upper()}")
    case_id: str
    case_version: int
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    status: ClarificationPlanStatus = ClarificationPlanStatus.QUESTIONS_REQUIRED
    round_number: int = 1
    rationale: str = ""
