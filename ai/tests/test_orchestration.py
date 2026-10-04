"""Unit Tests for Phase 6A: Case Orchestrator, State Machine, and Evidence Policy."""

from datetime import date
from decimal import Decimal
import pytest

from ai.app.assessment.contracts import (
    AssessmentFinding,
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    EpistemicLayer,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    EvidenceType,
    RuleOutcome,
    ThreeValuedLogic,
)
from ai.app.assessment.engine import DefaultAssessmentEngine
from ai.app.case.contracts import (
    CaseEventType,
    CaseState,
    CaseStatus,
    CaseVersionConflictError,
)
from ai.app.case.repository import InMemoryCaseRepository
from ai.app.evidence_policy.contracts import (
    Claim,
    ClaimStatus,
    EvidenceAuthorityScope,
    EvidenceResolutionPolicy,
)
from ai.app.evidence_policy.resolver import (
    EvidencePolicyRegistry,
    EvidencePolicyResolver,
)
from ai.app.extraction.document_extractor import DocumentExtractionPayload, DocumentSpan
from ai.app.orchestration.audit import AuditReconstructor
from ai.app.orchestration.contracts import (
    ActionTarget,
    CaseTurnResult,
    InvalidStateTransitionError,
    OrchestrationInputEvent,
)
from ai.app.orchestration.orchestrator import CaseOrchestrator
from ai.app.orchestration.state_machine import CaseStateMachine
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult


from ai.app.evaluation.assessment_cases import make_retrieval_result


def make_test_retrieval() -> RetrievalResponse:
    """Mock retrieval response with statutory SEBI DP charge ceiling rule."""
    item = make_retrieval_result(
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
    return RetrievalResponse(query="DP charges", results=[item])


@pytest.fixture
def orchestrator() -> CaseOrchestrator:
    repo = InMemoryCaseRepository()
    retrieval = make_test_retrieval()
    mock_retriever = type("MockRetriever", (), {"retrieve": lambda self, req: retrieval})()
    return CaseOrchestrator(repository=repo, retriever=mock_retriever)



# =====================================================================
# 1. State Machine Tests
# =====================================================================

def test_state_machine_valid_transitions():
    """Verify standard legitimate state transitions."""
    assert CaseStateMachine.can_transition(CaseStatus.DRAFT, CaseStatus.UNDER_ASSESSMENT)
    assert CaseStateMachine.can_transition(CaseStatus.UNDER_ASSESSMENT, CaseStatus.REQUIRES_CLARIFICATION)
    assert CaseStateMachine.can_transition(CaseStatus.REQUIRES_CLARIFICATION, CaseStatus.EVIDENCE_COLLECTION)
    assert CaseStateMachine.can_transition(CaseStatus.UNDER_ASSESSMENT, CaseStatus.RESOLVED)
    assert CaseStateMachine.can_transition(CaseStatus.RESOLVED, CaseStatus.REOPENED)
    assert CaseStateMachine.can_transition(CaseStatus.REOPENED, CaseStatus.UNDER_ASSESSMENT)


def test_state_machine_rejects_invalid_transitions():
    """Verify illegal transitions throw InvalidStateTransitionError."""
    # A resolved case cannot directly jump back to DRAFT or EVIDENCE_COLLECTION without REOPENED
    with pytest.raises(InvalidStateTransitionError):
        CaseStateMachine.validate_transition(CaseStatus.RESOLVED, CaseStatus.DRAFT)

    with pytest.raises(InvalidStateTransitionError):
        CaseStateMachine.validate_transition(CaseStatus.RESOLVED, CaseStatus.EVIDENCE_COLLECTION)


# =====================================================================
# 2. Evidence Policy & Claim Tests
# =====================================================================

def test_evidence_policy_field_specific_precedence():
    """Verify official document supersedes citizen narrative assertion for charged_amount."""
    resolver = EvidencePolicyResolver.default()

    ev_user = EvidenceItem(
        evidence_id="EV-USER-01",
        case_id="CASE-1",
        evidence_type=EvidenceType.USER_STATEMENT,
        field_name="charged_amount",
        value=Decimal("50.00"),
        source="user_complaint",
    )
    ev_doc = EvidenceItem(
        evidence_id="EV-DOC-01",
        case_id="CASE-1",
        evidence_type=EvidenceType.DOCUMENT,
        field_name="charged_amount",
        value=Decimal("15.00"),
        source="contract_note.pdf",
    )

    resolved = resolver.resolve_field("charged_amount", [ev_user, ev_doc])

    assert resolved.status == ClaimStatus.RESOLVED_BY_POLICY
    assert resolved.operative_value == Decimal("15.00")
    assert len(resolved.all_claims) == 2
    # Verify contradiction is preserved in claim audit trail
    assert len(resolved.contradicting_claim_ids) == 1


def test_evidence_policy_conflicting_documents_yields_contradicted():
    """Verify two conflicting official documents yield CONTRADICTED without guessing."""
    resolver = EvidencePolicyResolver.default()

    ev_doc1 = EvidenceItem(
        evidence_id="EV-DOC-01",
        case_id="CASE-1",
        evidence_type=EvidenceType.DOCUMENT,
        field_name="charged_amount",
        value=Decimal("15.00"),
        source="contract_note_1.pdf",
    )
    ev_doc2 = EvidenceItem(
        evidence_id="EV-DOC-02",
        case_id="CASE-1",
        evidence_type=EvidenceType.DOCUMENT,
        field_name="charged_amount",
        value=Decimal("20.00"),
        source="contract_note_2.pdf",
    )

    resolved = resolver.resolve_field("charged_amount", [ev_doc1, ev_doc2])

    assert resolved.status == ClaimStatus.CONTRADICTED
    assert resolved.operative_value is None
    assert len(resolved.contradicting_claim_ids) == 2


# =====================================================================
# 3. Orchestration Turn Lifecycle Tests
# =====================================================================

@pytest.mark.asyncio
async def test_orchestration_first_turn_clarification(orchestrator: CaseOrchestrator):
    """Test Turn 1: Incomplete complaint enters REQUIRES_CLARIFICATION with ActionIntent."""
    input_evt = OrchestrationInputEvent(
        complaint_text="Zerodha charged me ₹25 for a trade on 2026-09-12.",
        reference_date=date(2026, 9, 12),
    )

    result = await orchestrator.process_turn(
        case_id="CASE-ORCH-01",
        input_event=input_evt,
    )

    assert result.previous_version == 0
    assert result.new_version == 1
    assert result.new_status == CaseStatus.REQUIRES_CLARIFICATION
    assert len(result.clarification_plan.questions) > 0
    # Must generate an ActionIntent to request the missing document/info
    assert len(result.action_intents) > 0
    assert result.action_intents[0].action_type == "REQUEST_DOCUMENT"


@pytest.mark.asyncio
async def test_orchestration_second_turn_document_resolution(orchestrator: CaseOrchestrator):
    """Test Turn 2: Uploading contract note resolves case to VIOLATION_CONFIRMED."""
    # Turn 1
    input_1 = OrchestrationInputEvent(
        complaint_text="Zerodha charged me ₹25 for a trade on 2026-09-12.",
        reference_date=date(2026, 9, 12),
    )
    res_1 = await orchestrator.process_turn("CASE-ORCH-02", input_1)
    assert res_1.new_status == CaseStatus.REQUIRES_CLARIFICATION

    # Mock retrieval with SEBI rule
    retrieval = make_test_retrieval()
    orchestrator.retriever = type("MockRetriever", (), {"retrieve": lambda self, req: retrieval})()
    saved_state = await orchestrator.repository.get_case("CASE-ORCH-02")
    saved_state.retrieval_state = retrieval
    await orchestrator.repository.save_case(saved_state)

    # Turn 2: User provides contract note establishing delivery
    doc = DocumentExtractionPayload(
        document_id="CN-8891",
        raw_content="Trade Date: 2026-09-12\nType: Equity Delivery\nDP Charge: ₹25.00",
        content_format="pdf",
        spans=[DocumentSpan(text="Type: Equity Delivery", start_char=0, end_char=21)],
    )
    input_2 = OrchestrationInputEvent(
        user_message="Here is my contract note confirming equity delivery.",
        documents=[doc],
    )

    res_2 = await orchestrator.process_turn(
        case_id="CASE-ORCH-02",
        input_event=input_2,
        expected_version=1,
    )

    assert res_2.new_version == 2
    assert res_2.new_status == CaseStatus.RESOLVED
    assert res_2.assessment_result.status == AssessmentStatus.VIOLATION_CONFIRMED
    assert res_2.assessment_delta.status_changed is True
    assert "transaction_type" in res_2.assessment_delta.facts_changed
    assert res_2.assessment_delta.cause.get("outcome") == "VIOLATED"


@pytest.mark.asyncio
async def test_orchestration_case_reopening(orchestrator: CaseOrchestrator):
    """Test reopening a resolved case when new evidence arrives."""
    # Setup already resolved case
    state = CaseState(
        case_id="CASE-REOPEN-TEST",
        version=2,
        status=CaseStatus.RESOLVED,
        facts={"transaction_type": "equity_delivery", "charged_amount": Decimal("15.00")},
    )
    await orchestrator.repository.save_case(state)

    # Send new follow-up input
    input_evt = OrchestrationInputEvent(
        user_message="Wait, I just noticed an additional ₹10 fee charged on the ledger.",
    )

    result = await orchestrator.process_turn(
        case_id="CASE-REOPEN-TEST",
        input_event=input_evt,
        expected_version=2,
    )

    # Must have recorded CASE_REOPENED event
    event_types = [e.event_type for e in result.events_created]
    assert CaseEventType.CASE_REOPENED in event_types
    assert result.new_version == 3


@pytest.mark.asyncio
async def test_orchestration_optimistic_concurrency_conflict(orchestrator: CaseOrchestrator):
    """Test stale expected_version triggers CaseVersionConflictError."""
    input_1 = OrchestrationInputEvent(complaint_text="Complaint text.")
    await orchestrator.process_turn("CASE-CONCURRENCY", input_1)

    # Attempt turn with stale expected_version=0 when actual version is 1
    input_2 = OrchestrationInputEvent(user_message="Follow up.")
    with pytest.raises(CaseVersionConflictError):
        await orchestrator.process_turn(
            case_id="CASE-CONCURRENCY",
            input_event=input_2,
            expected_version=0,
        )


@pytest.mark.asyncio
async def test_orchestration_downstream_generation_failure_does_not_abort_assessment(orchestrator: CaseOrchestrator):
    """Verify presentation generation failure leaves assessment intact with generation_status=FAILED."""
    # Break generator deliberately
    orchestrator.generator = type(
        "FailingGenerator",
        (),
        {"generate_response": lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM API Timeout"))},
    )()

    input_evt = OrchestrationInputEvent(complaint_text="Complaint about ₹20 charge.")
    result = await orchestrator.process_turn("CASE-GEN-FAIL", input_evt)

    # Assessment must succeed and be persisted despite generator failure
    assert result.assessment_result is not None
    assert result.generated_response is None
    assert result.generation_snapshot.status == "FAILED"
    assert "LLM API Timeout" in (result.generation_snapshot.error_message or "")


@pytest.mark.asyncio
async def test_audit_reconstruction_completeness(orchestrator: CaseOrchestrator):
    """Verify AuditReconstructor verifies timeline and completeness."""
    input_1 = OrchestrationInputEvent(complaint_text="Initial complaint.")
    res = await orchestrator.process_turn("CASE-AUDIT", input_1)

    saved_state = await orchestrator.repository.get_case("CASE-AUDIT")
    report = AuditReconstructor.verify_audit_completeness(saved_state)

    assert report["is_complete"] is True
    assert report["events_count"] >= 1
    assert report["current_version"] == 1
    assert len(report["issues"]) == 0
