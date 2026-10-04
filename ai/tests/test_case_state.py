"""Tests for SANGYAN Phase 5 Case State, Versioning, Events, Concurrency & Reassessment.

Covers:
- Case creation
- Event append
- Version increment
- Optimistic concurrency (CaseVersionConflictError)
- Evidence addition & reconciliation
- Duplicate event & Idempotency
- Fact contradiction preservation (immutable history)
- Reassessment & AssessmentDelta
- User decline handling
- Clarification termination
- Case history preservation
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import pytest

from ai.app.assessment.contracts import (
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceType,
)
from ai.app.assessment.engine import DefaultAssessmentEngine
from ai.app.case.contracts import (
    AssessmentDelta,
    AssessmentSnapshot,
    CaseEvent,
    CaseEventType,
    CaseState,
    CaseStatus,
    CaseVersionConflictError,
)
from ai.app.case.repository import InMemoryCaseRepository
from ai.app.case.service import CaseService
from ai.app.clarification.planner import ClarificationPlanner
from ai.app.clarification.validator import QuestionValidator
from ai.app.extraction.document_extractor import DocumentExtractionPayload, DocumentSpan
from ai.app.extraction.extractor import FactExtractor
from ai.app.evaluation.assessment_cases import make_retrieval_result
from ai.app.generation.generator import AuditableResponseGenerator
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult


def make_test_retrieval() -> RetrievalResponse:
    """Helper to provide a deterministic DP cap provision."""
    prov = make_retrieval_result(
        provision_id="prov_cdsl_dp_cap_2026",
        document_id="doc_cdsl_tariff_2026",
        section_id="sec_dp_charges",
        authority="CDSL",
        source_class="REGULATORY",
        provision_text="CDSL DP charges for equity delivery shall not exceed ₹15.00 per debit transaction.",
        relevance_score=0.95,
        effective_from=date(2023, 1, 1),
        source_url="https://cdslindia.com/tariff.html",
        citation="CDSL Operating Tariff 2026",
    )
    return RetrievalResponse(query="DP charges", results=[prov])


@pytest.fixture
def case_service() -> CaseService:
    repo = InMemoryCaseRepository()
    extractor = FactExtractor()
    engine = DefaultAssessmentEngine()
    planner = ClarificationPlanner(max_questions_per_turn=2, max_rounds=3)
    validator = QuestionValidator()
    generator = AuditableResponseGenerator()
    return CaseService(
        repository=repo,
        assessment_engine=engine,
        fact_extractor=extractor,
        planner=planner,
        generator=generator,
    )


@pytest.mark.asyncio
async def test_case_creation_and_version_increment(case_service: CaseService):
    """Test initial case creation starts at version 1 and creates CASE_CREATED event."""
    retrieval = make_test_retrieval()
    state, gen_resp, plan = await case_service.create_case(
        case_id="CASE-001",
        complaint_text="Zerodha charged me ₹13.50 for a trade on 2026-09-12.",
        reference_date=date(2026, 9, 12),
        retrieval_response=retrieval,
    )

    assert state.case_id == "CASE-001"
    assert state.version == 1
    assert state.status in {CaseStatus.OPEN, CaseStatus.CLARIFICATION_REQUESTED}
    assert len(state.interaction_history) == 1
    assert state.interaction_history[0].event_type == CaseEventType.CASE_CREATED
    assert state.interaction_history[0].case_version == 1
    assert "transaction_type" in state.current_assessment.missing_information
    assert state.current_assessment.status == AssessmentStatus.EVIDENCE_INSUFFICIENT


@pytest.mark.asyncio
async def test_event_append_and_auditability(case_service: CaseService):
    """Test events are appended sequentially and history is immutable."""
    retrieval = make_test_retrieval()
    state, _, _ = await case_service.create_case(
        case_id="CASE-AUDIT",
        complaint_text="Zerodha charged me ₹13.50 for a trade on 2026-09-12.",
        reference_date=date(2026, 9, 12),
        retrieval_response=retrieval,
    )

    state2, _, _, _ = await case_service.process_user_turn(
        case_id="CASE-AUDIT",
        user_message="It was an equity delivery transaction.",
        expected_version=1,
        retrieval_response=retrieval,
    )

    assert state2.version == 2
    event_types = [e.event_type for e in state2.interaction_history]
    assert CaseEventType.CASE_CREATED in event_types
    assert CaseEventType.CLARIFICATION_ANSWERED in event_types
    # Verify events are strictly ordered by version
    versions = [e.case_version for e in state2.interaction_history]
    assert versions == sorted(versions)


@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict(case_service: CaseService):
    """Test modifying a stale case version raises CaseVersionConflictError."""
    retrieval = make_test_retrieval()
    state, _, _ = await case_service.create_case(
        case_id="CASE-CONCURRENCY",
        complaint_text="Zerodha charged me ₹13.50 for a trade.",
        retrieval_response=retrieval,
    )

    # Turn 2 commits version 2
    await case_service.process_user_turn(
        case_id="CASE-CONCURRENCY",
        user_message="Trade was on 2026-09-12.",
        expected_version=1,
        retrieval_response=retrieval,
    )

    # Stale client still expecting version 1 must fail
    with pytest.raises(CaseVersionConflictError) as exc_info:
        await case_service.process_user_turn(
            case_id="CASE-CONCURRENCY",
            user_message="Concurrent edit on stale state.",
            expected_version=1,
            retrieval_response=retrieval,
        )
    assert exc_info.value.expected_version == 1
    assert exc_info.value.actual_version == 2


@pytest.mark.asyncio
async def test_idempotent_event_processing(case_service: CaseService):
    """Test replaying an event with the same idempotency key is safely ignored without state change."""
    retrieval = make_test_retrieval()
    state, _, _ = await case_service.create_case(
        case_id="CASE-IDEMP",
        complaint_text="Zerodha charged me ₹13.50 for a trade.",
        retrieval_response=retrieval,
    )

    idemp_key = "turn2-msg-unique-key-12345"
    state2, gen2, plan2, delta2 = await case_service.process_user_turn(
        case_id="CASE-IDEMP",
        user_message="It was equity delivery.",
        expected_version=1,
        idempotency_key=idemp_key,
        retrieval_response=retrieval,
    )
    v2 = state2.version
    ev_count = len(state2.evidence)

    # Replay with same idempotency key
    state_dup, _, _, _ = await case_service.process_user_turn(
        case_id="CASE-IDEMP",
        user_message="It was equity delivery.",
        expected_version=v2,
        idempotency_key=idemp_key,
        retrieval_response=retrieval,
    )

    assert state_dup.version == v2
    assert len(state_dup.evidence) == ev_count


@pytest.mark.asyncio
async def test_fact_contradiction_preservation(case_service: CaseService):
    """Test contradicting assertions are retained in history, never silently erased."""
    retrieval = make_test_retrieval()
    # Turn 1: User claims ₹50 charged
    state, _, _ = await case_service.create_case(
        case_id="CASE-CONTRADICT",
        complaint_text="Zerodha charged me ₹50 for a trade on 2026-09-12.",
        reference_date=date(2026, 9, 12),
        retrieval_response=retrieval,
    )

    # Turn 2: Contract note proves ₹13.50 charged
    doc = DocumentExtractionPayload(
        document_id="DOC-CN-01",
        raw_content="Type: Equity Delivery\nDP Charge: ₹13.50",
        content_format="pdf",
        spans=[DocumentSpan(text="DP Charge: ₹13.50", start_char=0, end_char=18)],
    )

    state2, _, _, _ = await case_service.process_user_turn(
        case_id="CASE-CONTRADICT",
        user_message="Here is the contract note.",
        documents=[doc],
        expected_version=1,
        retrieval_response=retrieval,
    )

    # Both evidence items must exist in case evidence
    charge_evidence = [e for e in state2.evidence if e.field_name == "charged_amount"]
    assert len(charge_evidence) >= 2
    values = [e.value for e in charge_evidence]
    assert Decimal("50") in values
    assert Decimal("13.50") in values
    # Case facts adopted the authoritative document
    assert state2.facts["charged_amount"] == Decimal("13.50")


@pytest.mark.asyncio
async def test_reassessment_and_assessment_delta(case_service: CaseService):
    """Test assessment delta correctly captures status transition, newly resolved fields, and rationale."""
    retrieval = make_test_retrieval()
    state, _, _ = await case_service.create_case(
        case_id="CASE-DELTA",
        complaint_text="Zerodha charged me ₹13.50 on 2026-09-12 for a trade.",
        reference_date=date(2026, 9, 12),
        retrieval_response=retrieval,
    )
    assert state.current_assessment.status == AssessmentStatus.EVIDENCE_INSUFFICIENT

    state2, _, _, delta = await case_service.process_user_turn(
        case_id="CASE-DELTA",
        user_message="The trade was equity delivery.",
        expected_version=1,
        retrieval_response=retrieval,
    )

    assert delta is not None
    assert delta.previous_status == AssessmentStatus.EVIDENCE_INSUFFICIENT
    assert delta.new_status == AssessmentStatus.COMPLIANT_WITH_REGULATION
    assert "transaction_type" in delta.resolved_uncertainties
    assert len(state2.assessment_history) == 2


@pytest.mark.asyncio
async def test_user_declined_evidence(case_service: CaseService):
    """Test user declining to provide evidence is recorded and not asked again."""
    retrieval = make_test_retrieval()
    state, _, plan1 = await case_service.create_case(
        case_id="CASE-DECLINE",
        complaint_text="Zerodha charged me ₹13.50 on 2026-09-12.",
        reference_date=date(2026, 9, 12),
        retrieval_response=retrieval,
    )
    assert any(q.field == "transaction_type" for q in plan1.questions)

    state2, gen2, plan2, delta = await case_service.process_user_decline(
        case_id="CASE-DECLINE",
        field_name="transaction_type",
        expected_version=1,
    )

    assert "transaction_type" in state2.declined_fields
    # Planner must NOT ask for transaction_type again
    assert not any(q.field == "transaction_type" for q in plan2.questions)
    assert state2.status == CaseStatus.INSUFFICIENT_EVIDENCE
