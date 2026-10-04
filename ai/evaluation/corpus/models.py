"""Evaluation Case Data Models and Schemas for SANGYAN Phase 7A.

Epistemic foundation:
- Strongly typed Pydantic models for evaluation cases, expected reasoning stages,
  epistemic unknowns, fine-grained financial components, and verification results.
- Distinguishes necessary correctness from specific implementation paths.
- Uses Decimal for all monetary and quantitative amounts (zero float imprecision).
- Implements negative invariants: explicit 'expected_unknowns' to penalize hallucinations.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import AssessmentStatus, EvidenceType
from ai.app.extraction.contracts import FactEpistemicStatus
from ai.evaluation.corpus.taxonomy import (
    AdversarialSubtype,
    CaseCategory,
    CaseVisibility,
    ClaimRelationshipType,
    CompoundErrorType,
    DifficultyLevel,
    RetrievalFailureClass,
    RetrievalRelevance,
)


class ExpectedFact(BaseModel):
    """Specification of an expected empirical fact to be extracted."""
    field: str = Field(description="Canonical field name (e.g., 'charged_amount', 'transaction_type').")
    expected_value: Any = Field(description="Expected typed value (Decimal for money, date, string).")
    epistemic_status: FactEpistemicStatus = Field(
        default=FactEpistemicStatus.USER_ASSERTED,
        description="Expected epistemic status of the fact.",
    )
    required: bool = Field(default=True, description="Whether this fact is strictly mandatory for the case.")
    source_requirement: str | None = Field(
        default=None,
        description="Source identifier or type requirement (e.g. 'user_statement', 'contract_note').",
    )
    tolerance: Decimal | None = Field(
        default=None,
        description="Acceptable numeric absolute tolerance (Decimal) for financial amounts.",
    )
    data_type: str = Field(default="STRING", description="STRING, DECIMAL, DATE, BOOLEAN, etc.")


class ExpectedUnknown(BaseModel):
    """Negative invariant: fact that MUST remain unknown/null to avoid hallucination."""
    field: str = Field(description="Canonical field name that must NOT be hallucinated.")
    expected_value: None = Field(default=None, description="Must be None.")
    must_remain_unknown: bool = Field(default=True, description="Enforces penalty if any non-null fact is produced.")
    reason: str = Field(default="", description="Why this fact cannot be known from the given input.")


class ExpectedClaim(BaseModel):
    """Specification of an expected empirical claim submitted or extracted."""
    claim_id: str = Field(description="Logical identifier of the claim (e.g., 'CLM-01').")
    field_name: str = Field(description="Governed empirical field name.")
    claimed_value: Any = Field(description="Value asserted by this claim.")
    source_type: str = Field(default="USER_STATEMENT", description="Source of claim.")
    relationship_to: str | None = Field(default=None, description="Target claim_id if related.")
    relationship_type: ClaimRelationshipType | None = Field(
        default=None,
        description="CONTRADICTORY, SUPPORTING, SUPERSEDING, INDEPENDENT.",
    )
    expected_resolution: str | None = Field(
        default=None,
        description="Expected operative value after applying evidence policy.",
    )


class ExpectedIssue(BaseModel):
    """Specification of expected legal/regulatory issues to be identified."""
    primary_issue: str = Field(description="Core grievance issue that must be investigated.")
    secondary_issues: list[str] = Field(default_factory=list, description="Subordinate or derived issues.")
    irrelevant_plausible_issues: list[str] = Field(
        default_factory=list,
        description="Issues that appear plausible superficially but are legally irrelevant.",
    )
    acceptable_primary_alternatives: list[str] = Field(
        default_factory=list,
        description="Equally valid formulations or synonyms of the primary issue.",
    )


class ExpectedHypothesis(BaseModel):
    """Hypothesis tracking for complex multi-theory grievance cases."""
    hypothesis_id: str = Field(description="Logical identifier (e.g., 'H1').")
    description: str = Field(description="Explanation of the hypothesis.")
    required_evidence: list[str] = Field(default_factory=list, description="Evidence needed to sustain hypothesis.")
    supporting_provisions: list[str] = Field(default_factory=list, description="Provisions supporting this hypothesis.")
    disqualifying_evidence: list[str] = Field(default_factory=list, description="Evidence that disproves hypothesis.")
    expected_final_state: str = Field(
        default="UNRESOLVED",
        description="SUPPORTED, DISPROVED, UNRESOLVED.",
    )


class ExpectedSource(BaseModel):
    """Authoritative source document expected in the gold retrieval set."""
    source_id: str = Field(description="Document ID or identifier.")
    authority: str | None = Field(default=None, description="SEBI, CDSL, NSDL, etc.")
    organisation: str | None = Field(default=None, description="ORG_ZERODHA, ORG_ANGELONE, etc.")
    relevance: RetrievalRelevance = Field(default=RetrievalRelevance.REQUIRED)
    effective_date: date | None = None


class ExpectedProvision(BaseModel):
    """Authoritative regulatory or organisational provision expected in retrieval."""
    provision_id: str = Field(description="Exact provision ID in PostgreSQL or reference id.")
    source_document_id: str | None = None
    relevance: RetrievalRelevance = Field(default=RetrievalRelevance.REQUIRED)
    authority_class: str | None = None
    is_blocked_by_corpus_gap: bool = Field(
        default=False,
        description="Flagged true if required provision is absent from knowledge base.",
    )
    provenance_rationale: str = Field(
        default="",
        description="Statutory explanation of why this provision is required.",
    )


class ExpectedTemporalContext(BaseModel):
    """Temporal grounding specification for historical or amended regimes."""
    transaction_date: date | None = None
    complaint_date: date | None = None
    expected_rule_version: str | None = None
    is_superseded_at_transaction_date: bool = False
    applicable_circular_ref: str | None = None


class ExpectedCondition(BaseModel):
    """Governing statutory condition evaluation expectation."""
    condition_id: str
    description: str
    expected_boolean: bool | None = Field(
        default=None,
        description="True (met), False (failed), or None (UNKNOWN/insufficient evidence).",
    )
    operative_provision_id: str | None = None


class ExpectedFinancialBreakdown(BaseModel):
    """Fine-grained expected financial arithmetic using exact Decimal."""
    base_amount: Decimal | None = None
    brokerage: Decimal | None = None
    exchange_txn_charge: Decimal | None = None
    sebi_turnover_fee: Decimal | None = None
    gst: Decimal | None = None
    stt: Decimal | None = None
    stamp_duty: Decimal | None = None
    dp_charges: Decimal | None = None
    total_expected: Decimal | None = None
    components: dict[str, Decimal] = Field(default_factory=dict)
    known_error_trap: CompoundErrorType | None = None


class ExpectedAssessment(BaseModel):
    """Expected deterministic assessment determination and findings."""
    expected_status: AssessmentStatus
    acceptable_statuses: list[AssessmentStatus] = Field(default_factory=list)
    expected_findings: list[str] = Field(default_factory=list)
    expected_violations: list[str] = Field(default_factory=list)
    expected_remedy: str | None = None
    provenance_notes: str = ""


class ExpectedClarification(BaseModel):
    """Specification of expected clarification questions."""
    required_clarifications: list[str] = Field(
        default_factory=list,
        description="Mandatory questions/fields that must be clarified.",
    )
    acceptable_clarifications: list[str] = Field(
        default_factory=list,
        description="Acceptable alternate wordings or secondary clarifications.",
    )
    unnecessary_questions: list[str] = Field(
        default_factory=list,
        description="Irrelevant or already-answered questions that must NOT be asked.",
    )
    max_rounds_expected: int = Field(default=1)


class ExpectedGrounding(BaseModel):
    """Grounding and citation verification requirements."""
    unsupported_claim_penalty: bool = True
    required_citations: list[str] = Field(default_factory=list)
    prohibited_assertions: list[str] = Field(default_factory=list)


class MultiTurnTurn(BaseModel):
    """Specification of a dialogue turn in a multi-turn evaluation case."""
    turn_index: int
    user_message: str | None = None
    attached_documents: list[dict[str, Any]] = Field(default_factory=list)
    expected_status_after_turn: AssessmentStatus | None = None
    expected_facts_delta: dict[str, Any] = Field(default_factory=dict)
    expected_clarifications_asked: list[str] = Field(default_factory=list)


class EvaluationCase(BaseModel):
    """Strongly typed, canonical evaluation case for SANGYAN."""
    case_id: str = Field(description="Unique case identifier (e.g. 'BASIC-001', 'TEMP-004').")
    title: str = Field(description="Concise descriptive title of the grievance case.")
    category: CaseCategory = Field(description="Primary category.")
    secondary_categories: list[CaseCategory] = Field(default_factory=list)
    difficulty: DifficultyLevel = Field(description="Difficulty rating (L1 - L6).")
    adversarial_subtype: AdversarialSubtype | None = None

    language: str = Field(default="en", description="Source text language: 'en', 'hi', 'hinglish'.")
    user_input: str = Field(description="Raw grievance text as submitted by investor.")
    visibility: CaseVisibility = Field(default=CaseVisibility.PUBLIC)

    context: dict[str, Any] = Field(default_factory=dict, description="Metadata, session state, etc.")
    expected_facts: list[ExpectedFact] = Field(default_factory=list)
    expected_unknowns: list[ExpectedUnknown] = Field(default_factory=list)
    expected_claims: list[ExpectedClaim] = Field(default_factory=list)

    expected_issues: ExpectedIssue | None = None
    expected_hypotheses: list[ExpectedHypothesis] = Field(default_factory=list)

    expected_sources: list[ExpectedSource] = Field(default_factory=list)
    expected_provisions: list[ExpectedProvision] = Field(default_factory=list)
    acceptable_provisions: list[str] = Field(
        default_factory=list,
        description="Equally valid alternative provision IDs.",
    )

    expected_temporal_context: ExpectedTemporalContext | None = None
    expected_conditions: list[ExpectedCondition] = Field(default_factory=list)
    expected_financial: ExpectedFinancialBreakdown | None = None

    expected_assessment: ExpectedAssessment | None = None
    expected_clarifications: ExpectedClarification | None = None
    expected_grounding: ExpectedGrounding | None = None

    multi_turn_flow: list[MultiTurnTurn] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    is_blocked_by_corpus_gap: bool = Field(
        default=False,
        description="Flagged true if case tests an unindexed regulatory regime.",
    )
    corpus_gap_reason: str | None = None


# Evaluation Output Contracts

class StageEvaluationResult(BaseModel):
    """Granular verification results for a single reasoning stage."""
    stage_name: str
    passed: bool
    score: float = 1.0
    details: dict[str, Any] = Field(default_factory=dict)
    discrepancies: list[str] = Field(default_factory=list)
    failure_class: str | None = None


class CaseEvaluationReport(BaseModel):
    """Comprehensive evaluation record for a single evaluation case."""
    case_id: str
    title: str
    category: CaseCategory
    difficulty: DifficultyLevel
    overall_passed: bool
    stages: dict[str, StageEvaluationResult] = Field(default_factory=dict)
    false_violation: bool = False
    false_compliance: bool = False
    failure_class: str | None = None
    latency_ms: float = 0.0
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BenchmarkSuiteReport(BaseModel):
    """Aggregate benchmark run results across the corpus."""
    suite_id: str
    benchmark_version: str = "7A-1.0"
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    accuracy: float = 0.0

    # Stage-level metrics
    fact_accuracy: float = 0.0
    fact_unknown_accuracy: float = 0.0
    issue_precision: float = 0.0
    issue_recall: float = 0.0
    retrieval_recall_at_1: float = 0.0
    retrieval_recall_at_5: float = 0.0
    retrieval_recall_at_10: float = 0.0
    retrieval_recall_at_20: float = 0.0
    retrieval_mrr: float = 0.0
    retrieval_ndcg_at_10: float = 0.0
    retrieval_required_recall: float = 0.0
    authority_correctness: float = 0.0
    organisation_correctness: float = 0.0
    temporal_correctness: float = 0.0
    evidence_contradiction_accuracy: float = 0.0
    assessment_status_accuracy: float = 0.0
    condition_accuracy: float = 0.0
    numerical_accuracy: float = 0.0
    clarification_precision: float = 0.0
    clarification_recall: float = 0.0
    unnecessary_question_rate: float = 0.0
    grounding_unsupported_claim_rate: float = 0.0

    # Safety invariants
    false_positive_violations: int = 0
    false_positive_compliances: int = 0

    # Breakdown by difficulty
    difficulty_performance: dict[str, dict[str, Any]] = Field(default_factory=dict)

    # Breakdown by category
    category_performance: dict[str, dict[str, Any]] = Field(default_factory=dict)

    # Failure classifications tally
    failure_class_counts: dict[str, int] = Field(default_factory=dict)

    # Individual case reports
    cases: list[CaseEvaluationReport] = Field(default_factory=list)

    # Metadata for reproducibility
    metadata: dict[str, Any] = Field(default_factory=dict)
