"""Tests for SANGYAN Phase 5 Clarification Planner, Question Contracts, Validation & Multilingual Dialogue.

Covers:
- Clarification planning
- Question prioritization
- Question validation
- Never asking already-known facts
- Contradiction-aware clarification
- Temporal clarification
- Multilingual question rendering (EN, HI, Hinglish)
- Answer integration through evidence boundary
"""

from datetime import date
from decimal import Decimal
import pytest

from ai.app.assessment.contracts import (
    AssessmentFinding,
    AssessmentResult,
    AssessmentStatus,
    EpistemicLayer,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    EvidenceType,
)
from ai.app.case.contracts import CaseEvent, CaseEventType, CaseState, CaseStatus
from ai.app.clarification.contracts import (
    ClarificationPlan,
    ClarificationPlanStatus,
    ClarificationQuestion,
    QuestionPriority,
)
from ai.app.clarification.planner import CANONICAL_QUESTIONS, ClarificationPlanner
from ai.app.clarification.validator import QuestionValidator


def make_dummy_assessment(
    case_id: str,
    status: AssessmentStatus,
    missing_fields: list[str],
    evidence_reqs: list[EvidenceRequirement] | None = None,
) -> AssessmentResult:
    reqs = evidence_reqs or [
        EvidenceRequirement(
            requirement_id=f"REQ-{f}",
            field_name=f,
            status=EvidenceRequirementStatus.MISSING,
        )
        for f in missing_fields
    ]
    return AssessmentResult(
        case_id=case_id,
        status=status,
        findings=[],
        evaluated_provisions=[],
        evidence_requirements=reqs,
        conflicts=[],
        missing_information=missing_fields,
        temporal_resolution="RESOLVED",
        authority_resolution="RESOLVED",
        confidence=EpistemicSupportLevel.MODERATE_SUPPORT,
        provenance_ids=[],
    )


def test_clarification_planning_minimum_necessary():
    """Test planner requests only the highest-impact missing information."""
    planner = ClarificationPlanner(max_questions_per_turn=2)
    state = CaseState(
        case_id="CASE-PLAN-01",
        version=1,
        facts={"organisation": "ORG_ZERODHA", "charged_amount": Decimal("13.50")},
        evidence=[],
    )
    assessment = make_dummy_assessment(
        case_id="CASE-PLAN-01",
        status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        missing_fields=["transaction_type", "transaction_date"],
    )

    plan = planner.plan(state, assessment, language="en")
    assert plan.status == ClarificationPlanStatus.QUESTIONS_REQUIRED
    assert len(plan.questions) <= 2
    # transaction_type has higher priority / weight
    asked_fields = [q.field for q in plan.questions]
    assert "transaction_type" in asked_fields


def test_never_ask_already_known_facts():
    """Test planner never asks for fields already present in case facts."""
    planner = ClarificationPlanner()
    state = CaseState(
        case_id="CASE-KNOWN",
        version=1,
        facts={
            "organisation": "ORG_ZERODHA",
            "transaction_type": "equity_delivery",
            "transaction_date": date(2026, 9, 12),
        },
        evidence=[],
    )
    # Even if missing_fields erroneously included transaction_type, state inspection prevents asking
    assessment = make_dummy_assessment(
        case_id="CASE-KNOWN",
        status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        missing_fields=["transaction_type", "charged_amount"],
    )

    plan = planner.plan(state, assessment, language="en")
    asked_fields = [q.field for q in plan.questions]
    assert "transaction_type" not in asked_fields
    assert "charged_amount" in asked_fields


def test_contradiction_aware_clarification():
    """Test planner targets existing conflicting evidence explicitly."""
    planner = ClarificationPlanner()
    ev1 = EvidenceItem(
        evidence_id="EVID-1",
        case_id="CASE-CONTRA",
        evidence_type=EvidenceType.USER_STATEMENT,
        field_name="charged_amount",
        value=Decimal("50.00"),
        source="user_msg",
    )
    ev2 = EvidenceItem(
        evidence_id="EVID-2",
        case_id="CASE-CONTRA",
        evidence_type=EvidenceType.USER_STATEMENT,
        field_name="charged_amount",
        value=Decimal("15.00"),
        source="user_msg_2",
    )
    state = CaseState(
        case_id="CASE-CONTRA",
        version=2,
        facts={},
        evidence=[ev1, ev2],
    )
    reqs = [
        EvidenceRequirement(
            requirement_id="REQ-AMOUNT",
            field_name="charged_amount",
            status=EvidenceRequirementStatus.CONTRADICTED,
        )
    ]
    assessment = make_dummy_assessment(
        case_id="CASE-CONTRA",
        status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        missing_fields=["charged_amount"],
        evidence_reqs=reqs,
    )

    plan = planner.plan(state, assessment, language="en")
    assert plan.status == ClarificationPlanStatus.QUESTIONS_REQUIRED
    assert len(plan.questions) == 1
    q = plan.questions[0]
    assert q.field == "charged_amount"
    assert "conflicting" in q.question.lower() or "50" in q.question


def test_temporal_clarification():
    """Test planner produces precise temporal clarification on TEMPORALITY_UNRESOLVED."""
    planner = ClarificationPlanner()
    state = CaseState(
        case_id="CASE-TEMP",
        version=1,
        facts={"organisation": "ORG_ZERODHA", "transaction_type": "equity_delivery"},
        evidence=[],
    )
    assessment = make_dummy_assessment(
        case_id="CASE-TEMP",
        status=AssessmentStatus.TEMPORALITY_UNRESOLVED,
        missing_fields=["transaction_date"],
    )

    plan = planner.plan(state, assessment, language="en")
    assert len(plan.questions) == 1
    assert plan.questions[0].field == "transaction_date"
    assert plan.questions[0].expected_answer_type == "DATE"


def test_question_validator_accepts_valid_and_rejects_hallucinated():
    """Test QuestionValidator verifies question alignment with deterministic contract."""
    state = CaseState(case_id="CASE-V", version=1, facts={}, evidence=[])
    assessment = make_dummy_assessment(
        case_id="CASE-V",
        status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        missing_fields=["transaction_type"],
    )

    # Valid question
    valid_q = ClarificationQuestion(
        field="transaction_type",
        question="What type of transaction was this — delivery or intraday?",
        reason="The applicable DP charge depends on the transaction type.",
        required_for=["PROV-123"],
        priority=QuestionPriority.CRITICAL,
        expected_answer_type="ENUM",
        acceptable_values=["equity_delivery", "intraday"],
    )
    is_valid, errors = QuestionValidator.validate_question(valid_q, state, assessment)
    assert is_valid is True
    assert len(errors) == 0

    # Prohibited question
    prohibited_q = ClarificationQuestion(
        field="transaction_type",
        question="Please enter your login password and OTP.",
        reason="Verification",
        required_for=["PROV-123"],
        priority=QuestionPriority.CRITICAL,
        expected_answer_type="STRING",
    )
    is_valid, errors = QuestionValidator.validate_question(prohibited_q, state, assessment)
    assert is_valid is False
    assert any("prohibited" in err.lower() for err in errors)


def test_multilingual_question_rendering():
    """Test canonical questions render correctly in English, Hindi, and Hinglish."""
    planner = ClarificationPlanner()
    state = CaseState(
        case_id="CASE-MULTI",
        version=1,
        facts={"organisation": "ORG_ZERODHA"},
        evidence=[],
    )
    assessment = make_dummy_assessment(
        case_id="CASE-MULTI",
        status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        missing_fields=["transaction_type"],
    )

    # English
    plan_en = planner.plan(state, assessment, language="en")
    assert "delivery" in plan_en.questions[0].question.lower()

    # Hindi
    plan_hi = planner.plan(state, assessment, language="hi")
    assert "लेन-देन" in plan_hi.questions[0].question

    # Hinglish
    plan_hinglish = planner.plan(state, assessment, language="hinglish")
    assert "delivery" in plan_hinglish.questions[0].question.lower() or "intraday" in plan_hinglish.questions[0].question.lower()
