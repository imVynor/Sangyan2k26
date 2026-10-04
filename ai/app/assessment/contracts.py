"""Epistemic Assessment Contracts and Controlled Vocabularies for SANGYAN.

Epistemic foundation:
- CASE FACTS + EVIDENCE + RETRIEVED PROVISIONS -> DETERMINISTIC ASSESSMENT.
- Never collapse Observed, Derived, Retrieved, Interpreted, and Assessed layers.
- Three-valued logic: TRUE, FALSE, UNKNOWN.
- Never convert EVIDENCE_INSUFFICIENT or REGULATORY_COVERAGE_UNRESOLVED into COMPLIANT.
- Safety invariant: COMPLIANT_WITH_REGULATION requires affirmative proof.
- Safety invariant: VIOLATION_CONFIRMED requires all governing conditions to be TRUE (never UNKNOWN).
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol, Sequence
from pydantic import BaseModel, Field, field_validator

from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.source_classes import SourceClass
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult


class AssessmentStatus(str, Enum):
    """Controlled vocabulary for SANGYAN assessment determinations."""
    VIOLATION_CONFIRMED = "VIOLATION_CONFIRMED"
    COMPLIANT_WITH_REGULATION = "COMPLIANT_WITH_REGULATION"
    ORGANISATION_POLICY_DEVIATION = "ORGANISATION_POLICY_DEVIATION"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    REGULATORY_COVERAGE_UNRESOLVED = "REGULATORY_COVERAGE_UNRESOLVED"
    TEMPORALITY_UNRESOLVED = "TEMPORALITY_UNRESOLVED"
    AUTHORITY_UNRESOLVED = "AUTHORITY_UNRESOLVED"
    CONFLICTING_PROVISIONS = "CONFLICTING_PROVISIONS"


class EpistemicLayer(str, Enum):
    """Categorical distinction of epistemically separated knowledge layers."""
    OBSERVED = "OBSERVED"        # Directly supported by case evidence (e.g. charged ₹20)
    DERIVED = "DERIVED"          # Deterministically calculated from observed facts (e.g. 20 > 15)
    RETRIEVED = "RETRIEVED"      # Authoritative statements from knowledge provisions
    INTERPRETED = "INTERPRETED"  # Model-assisted interpretation (explicitly marked)
    ASSESSED = "ASSESSED"        # Final deterministic determination


class EpistemicSupportLevel(str, Enum):
    """Controlled qualitative confidence level based on evidentiary support."""
    HIGH_SUPPORT = "HIGH_SUPPORT"
    MODERATE_SUPPORT = "MODERATE_SUPPORT"
    LOW_SUPPORT = "LOW_SUPPORT"
    INSUFFICIENT_SUPPORT = "INSUFFICIENT_SUPPORT"


class EvidenceType(str, Enum):
    """Taxonomy of evidentiary material submitted for a case."""
    USER_STATEMENT = "USER_STATEMENT"
    DOCUMENT = "DOCUMENT"
    SCREENSHOT = "SCREENSHOT"
    TRANSACTION_RECORD = "TRANSACTION_RECORD"
    INVOICE = "INVOICE"
    BROKER_STATEMENT = "BROKER_STATEMENT"
    EMAIL = "EMAIL"
    SYSTEM_RECORD = "SYSTEM_RECORD"
    EXTERNAL_SOURCE = "EXTERNAL_SOURCE"


class ThreeValuedLogic(str, Enum):
    """Kleene three-valued logic state."""
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"

    def __and__(self, other: "ThreeValuedLogic") -> "ThreeValuedLogic":
        if self == ThreeValuedLogic.FALSE or other == ThreeValuedLogic.FALSE:
            return ThreeValuedLogic.FALSE
        if self == ThreeValuedLogic.UNKNOWN or other == ThreeValuedLogic.UNKNOWN:
            return ThreeValuedLogic.UNKNOWN
        return ThreeValuedLogic.TRUE

    def __or__(self, other: "ThreeValuedLogic") -> "ThreeValuedLogic":
        if self == ThreeValuedLogic.TRUE or other == ThreeValuedLogic.TRUE:
            return ThreeValuedLogic.TRUE
        if self == ThreeValuedLogic.UNKNOWN or other == ThreeValuedLogic.UNKNOWN:
            return ThreeValuedLogic.UNKNOWN
        return ThreeValuedLogic.FALSE

    def __invert__(self) -> "ThreeValuedLogic":
        if self == ThreeValuedLogic.TRUE:
            return ThreeValuedLogic.FALSE
        if self == ThreeValuedLogic.FALSE:
            return ThreeValuedLogic.TRUE
        return ThreeValuedLogic.UNKNOWN


class EvidenceItem(BaseModel):
    """Unit of case evidence representing an observed empirical assertion."""
    evidence_id: str = Field(description="Unique identifier for this evidence item (e.g. 'EVID-001').")
    case_id: str = Field(description="Associated case identifier.")
    evidence_type: EvidenceType = Field(description="Category of evidence.")
    field_name: str = Field(description="Target fact/field (e.g. 'charged_amount', 'transaction_date', 'transaction_type').")
    value: Any = Field(description="Observed value (Decimal for money, date for dates, str/bool for categories).")
    source: str = Field(description="Origin of this evidence item (e.g. 'contract_note.pdf', 'user_complaint').")
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_date: date | None = Field(default=None, description="Date when the observed event occurred.")
    confidence: EpistemicSupportLevel = Field(default=EpistemicSupportLevel.HIGH_SUPPORT)
    provenance: dict[str, Any] = Field(default_factory=dict, description="Metadata or SHA-256 hash of original file.")


class EvidenceRequirementStatus(str, Enum):
    """Evidentiary state of a required input field."""
    KNOWN = "KNOWN"
    MISSING = "MISSING"
    CONTRADICTED = "CONTRADICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceRequirement(BaseModel):
    """Specification of an evidentiary input required to evaluate a provision."""
    field_name: str = Field(description="Target field required by the provision.")
    description: str | None = Field(default=None, description="Human/LLM understandable explanation.")
    status: EvidenceRequirementStatus = Field(default=EvidenceRequirementStatus.MISSING)
    evidence_ids: list[str] = Field(default_factory=list, description="IDs of matching evidence items if known.")


class ConditionOperator(str, Enum):
    """Controlled operators for deterministic condition evaluation."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_OR_EQUAL = "less_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    DATE_BEFORE = "date_before"
    DATE_AFTER = "date_after"
    DATE_BETWEEN = "date_between"


class ConditionEvaluation(BaseModel):
    """Deterministic evaluation of a single rule condition against case evidence."""
    condition_id: str
    field: str
    operator: ConditionOperator
    target_value: Any
    observed_value: Any
    result: ThreeValuedLogic
    evidence_ids: list[str] = Field(default_factory=list)
    derived_reason: str | None = None


class ExceptionEvaluation(BaseModel):
    """Evaluation of an explicit statutory or procedural exception clause."""
    exception_id: str
    description: str
    applies: ThreeValuedLogic
    conditions: list[ConditionEvaluation] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str | None = None


class RuleOutcome(str, Enum):
    """Outcome of evaluating a provision against a case."""
    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class ApplicabilityEvaluation(BaseModel):
    """Comprehensive applicability and rule evaluation for a single provision."""
    provision_id: str
    relevance_score: float = 0.0
    temporal_status: str = Field(description="APPLICABLE, NOT_APPLICABLE, or TEMPORALITY_UNRESOLVED.")
    authority_status: str = Field(description="APPLICABLE, NOT_APPLICABLE, or AUTHORITY_UNRESOLVED.")
    source_class: str = Field(default="REGULATORY")
    rule_outcome: RuleOutcome = Field(default=RuleOutcome.UNKNOWN)
    overall_applicability: str = Field(default="UNKNOWN", description="APPLICABLE, NOT_APPLICABLE, or UNRESOLVED.")
    conditions: list[ConditionEvaluation] = Field(default_factory=list)
    exceptions: list[ExceptionEvaluation] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    evaluation_notes: str | None = None


class ConflictResolutionBasis(str, Enum):
    """Legal basis utilized to resolve conflicting provisions."""
    TEMPORAL_SUPERSEDED = "TEMPORAL_SUPERSEDED"
    AUTHORITY_HIERARCHY = "AUTHORITY_HIERARCHY"
    SPECIFICITY = "SPECIFICITY"
    EXCEPTION = "EXCEPTION"
    AMENDMENT = "AMENDMENT"
    UNRESOLVED = "UNRESOLVED"


class Conflict(BaseModel):
    """Explicit representation of conflicting retrieved provisions."""
    conflict_id: str
    provision_ids: list[str]
    nature_of_conflict: str
    resolution_attempted: bool = True
    resolved: bool = False
    prevailing_provision_id: str | None = None
    resolution_basis: ConflictResolutionBasis = ConflictResolutionBasis.UNRESOLVED
    explanation: str | None = None


class AssessmentFinding(BaseModel):
    """Discrete, provenance-grounded assessment finding."""
    finding_id: str
    epistemic_layer: EpistemicLayer
    normative_source: str = Field(description="REGULATORY, ORGANISATION_POLICY, ORGANISATION_PROCEDURE, etc.")
    status: AssessmentStatus
    statement: str
    provision_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: EpistemicSupportLevel = EpistemicSupportLevel.HIGH_SUPPORT


class AssessmentRequest(BaseModel):
    """Structured request for epistemic assessment."""
    case_id: str
    case_facts: dict[str, Any] = Field(default_factory=dict, description="Structured observed case facts.")
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    retrieval_response: RetrievalResponse
    incident_date: date | None = None
    target_organisation: str | None = None
    require_regulatory_coverage: bool = True
    operative_claims: list[Any] = Field(default_factory=list, description="Resolved operative claims per field.")
    claims: list[Any] = Field(default_factory=list, description="Historical and active claims for audit.")


class AssessmentResult(BaseModel):
    """Structured, auditable assessment result for SANGYAN."""
    case_id: str
    status: AssessmentStatus
    findings: list[AssessmentFinding] = Field(default_factory=list)
    evaluated_provisions: list[ApplicabilityEvaluation] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    temporal_resolution: str = "RESOLVED"
    authority_resolution: str = "RESOLVED"
    confidence: EpistemicSupportLevel = EpistemicSupportLevel.HIGH_SUPPORT
    provenance_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
