"""Targeted Tests for SANGYAN Phase 7D: Evidence Resolution & Contradiction Reasoning.

Epistemic invariants tested:
1. User ₹500 -> Document ₹300: ₹500 CONTRADICTED, ₹300 OPERATIVE.
2. User ₹500 -> No document: ₹500 retained as operative.
3. User ₹500 -> Document order value ₹500: No contradiction across distinct semantic fields.
4. User says brokerage -> Document says DP charge: Reconciled per charge event.
5. Multi-turn: Turn 1 user assertion -> Turn 2 document evidence -> Turn 3 assessment uses operative claim.
6. Document evidence without user claim: Directly usable as operative.
7. Safety invariant: Unknowns remain safe (EVIDENCE_INSUFFICIENT) without forced resolution.
"""

from decimal import Decimal
import pytest

from ai.app.assessment.contracts import (
    AssessmentRequest,
    AssessmentStatus,
    EvidenceItem,
    EvidenceRequirementStatus,
    EvidenceType,
)
from ai.app.assessment.engine import DefaultAssessmentEngine
from ai.app.assessment.evidence_manager import EvidenceManager
from ai.app.evidence_policy.contracts import Claim, ClaimStatus
from ai.app.evidence_policy.resolver import EvidencePolicyResolver
from ai.app.extraction.document_extractor import DocumentExtractionPayload, DocumentSpan
from ai.app.orchestration.contracts import OrchestrationInputEvent
from ai.app.orchestration.orchestrator import CaseOrchestrator
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult


def test_1_user_claim_contradicted_by_document():
    """Test 1: User ₹500 -> document ₹300. Expected: ₹500 = CONTRADICTED, ₹300 = OPERATIVE."""
    resolver = EvidencePolicyResolver.default()

    ev_user = EvidenceItem(
        evidence_id="EV-USER-500",
        case_id="CASE-T1",
        evidence_type=EvidenceType.USER_STATEMENT,
        field_name="charged_amount",
        value=Decimal("500.00"),
        source="user_assertion",
    )
    ev_doc = EvidenceItem(
        evidence_id="EV-DOC-300",
        case_id="CASE-T1",
        evidence_type=EvidenceType.DOCUMENT,
        field_name="charged_amount",
        value=Decimal("300.00"),
        source="contract_note.pdf",
    )

    resolved = resolver.resolve_field("charged_amount", [ev_user, ev_doc])

    assert resolved.status == ClaimStatus.RESOLVED_BY_POLICY
    assert resolved.operative_value == Decimal("300.00")
    # Verify ₹500 is marked CONTRADICTED in claims
    user_claims = [c for c in resolved.all_claims if c.claimed_value == Decimal("500.00")]
    assert len(user_claims) == 1
    assert user_claims[0].status == ClaimStatus.CONTRADICTED

    # Verify ₹300 is marked RESOLVED_BY_POLICY / SUPPORTED
    doc_claims = [c for c in resolved.all_claims if c.claimed_value == Decimal("300.00")]
    assert len(doc_claims) == 1
    assert doc_claims[0].status == ClaimStatus.RESOLVED_BY_POLICY
    assert doc_claims[0].claim_id in resolved.supporting_claim_ids
    assert user_claims[0].claim_id in resolved.contradicting_claim_ids


def test_2_user_claim_retained_when_no_document():
    """Test 2: User ₹500 -> no document. Expected: ₹500 retained."""
    resolver = EvidencePolicyResolver.default()

    ev_user = EvidenceItem(
        evidence_id="EV-USER-500",
        case_id="CASE-T2",
        evidence_type=EvidenceType.USER_STATEMENT,
        field_name="charged_amount",
        value=Decimal("500.00"),
        source="user_assertion",
    )

    resolved = resolver.resolve_field("charged_amount", [ev_user])

    assert resolved.status == ClaimStatus.SUPPORTED
    assert resolved.operative_value == Decimal("500.00")
    assert len(resolved.contradicting_claim_ids) == 0


def test_3_no_contradiction_between_distinct_semantic_roles():
    """Test 3: User ₹500 (charged_amount) -> Document ₹500 (order_value). Expected: NO CONTRADICTION."""
    resolver = EvidencePolicyResolver.default()

    ev_charge = EvidenceItem(
        evidence_id="EV-CHARGE-500",
        case_id="CASE-T3",
        evidence_type=EvidenceType.USER_STATEMENT,
        field_name="charged_amount",
        value=Decimal("500.00"),
        source="user_assertion",
    )
    ev_order = EvidenceItem(
        evidence_id="EV-ORDER-500",
        case_id="CASE-T3",
        evidence_type=EvidenceType.DOCUMENT,
        field_name="order_value",
        value=Decimal("500.00"),
        source="contract_note.pdf",
    )

    resolved_charge = resolver.resolve_field("charged_amount", [ev_charge, ev_order])
    resolved_order = resolver.resolve_field("order_value", [ev_charge, ev_order])

    # Distinct fields must never contradict each other
    assert resolved_charge.status == ClaimStatus.SUPPORTED
    assert resolved_charge.operative_value == Decimal("500.00")
    assert len(resolved_charge.contradicting_claim_ids) == 0

    assert resolved_order.status == ClaimStatus.SUPPORTED
    assert resolved_order.operative_value == Decimal("500.00")
    assert len(resolved_order.contradicting_claim_ids) == 0


def test_4_brokerage_vs_dp_charge_event_reconciliation():
    """Test 4: User says brokerage -> document says DP charge for the charge event."""
    resolver = EvidencePolicyResolver.default()

    ev_user_charge = EvidenceItem(
        evidence_id="EV-USER-CHG",
        case_id="CASE-T4",
        evidence_type=EvidenceType.USER_STATEMENT,
        field_name="charge_type",
        value="brokerage",
        source="user_assertion",
    )
    ev_doc_charge = EvidenceItem(
        evidence_id="EV-DOC-CHG",
        case_id="CASE-T4",
        evidence_type=EvidenceType.DOCUMENT,
        field_name="charge_type",
        value="dp_charges",
        source="contract_note.pdf",
    )

    resolved = resolver.resolve_field("charge_type", [ev_user_charge, ev_doc_charge])

    assert resolved.status == ClaimStatus.RESOLVED_BY_POLICY
    assert resolved.operative_value == "dp_charges"
    user_claims = [c for c in resolved.all_claims if c.claimed_value == "brokerage"]
    assert user_claims[0].status == ClaimStatus.CONTRADICTED


@pytest.mark.asyncio
async def test_5_multiturn_precedence_and_assessment():
    """Test 5: Multi-turn:
    turn 1 -> user assertion (₹500)
    turn 2 -> document evidence (₹300)
    turn 3 -> assessment consumes resolved operative claim (₹300).
    """
    orchestrator = CaseOrchestrator()
    case_id = "CASE-PHASE7D-MULTITURN"

    # Turn 1: User says broker charged ₹500
    res_t1 = await orchestrator.process_turn(
        case_id=case_id,
        input_event=OrchestrationInputEvent(
            complaint_text="Zerodha charged me Rs 500 fees on 2026-03-01 for equity delivery.",
            user_message="Zerodha charged me Rs 500 fees on 2026-03-01 for equity delivery.",
        ),
    )
    assert res_t1.new_facts.get("charged_amount") == Decimal("500.00")

    # Turn 2: User provides contract note with ₹300
    doc_text = "CONTRACT NOTE\nBroker: Zerodha Broking Ltd\nDate: 2026-03-01\nTotal Charges: Rs 300.00\nCharged Amount: Rs 300.00"
    doc_payload = DocumentExtractionPayload(
        document_id="DOC-CN-300",
        raw_content=doc_text,
        content_format="text",
        spans=[DocumentSpan(text=doc_text, page_number=1)],
    )

    res_t2 = await orchestrator.process_turn(
        case_id=case_id,
        input_event=OrchestrationInputEvent(
            complaint_text="Here is my contract note.",
            user_message="I checked the contract note. It says Rs 300.",
            documents=[doc_payload],
        ),
    )

    # In turn 2, operative fact must be ₹300, and historical ₹500 is preserved in claims
    assert res_t2.new_facts.get("charged_amount") == Decimal("300.00")
    all_claims = res_t2.claims
    c500 = [c for c in all_claims if str(c.claimed_value) in {"500", "500.00"}]
    c300 = [c for c in all_claims if str(c.claimed_value) in {"300", "300.00"}]
    assert len(c500) >= 1
    assert len(c300) >= 1
    assert c500[0].status == ClaimStatus.CONTRADICTED
    assert c300[0].status in {ClaimStatus.RESOLVED_BY_POLICY, ClaimStatus.SUPPORTED}

    # Turn 3: Follow-up question, assessment must consume operative claim ₹300
    res_t3 = await orchestrator.process_turn(
        case_id=case_id,
        input_event=OrchestrationInputEvent(
            user_message="Please confirm the assessment on this charge.",
        ),
    )
    assert res_t3.new_facts.get("charged_amount") == Decimal("300.00")


def test_6_document_evidence_without_user_claim():
    """Test 6: Document evidence with no user claim is directly usable without requiring user claim."""
    resolver = EvidencePolicyResolver.default()

    ev_doc = EvidenceItem(
        evidence_id="EV-DOC-ONLY",
        case_id="CASE-T6",
        evidence_type=EvidenceType.DOCUMENT,
        field_name="charged_amount",
        value=Decimal("20.00"),
        source="broker_ledger.pdf",
    )

    resolved = resolver.resolve_field("charged_amount", [ev_doc])

    assert resolved.status == ClaimStatus.SUPPORTED
    assert resolved.operative_value == Decimal("20.00")
    assert len(resolved.all_claims) == 1
    assert len(resolved.supporting_claim_ids) == 1
    assert len(resolved.contradicting_claim_ids) == 0


def test_7_safety_invariant_unknown_retains_evidence_insufficient():
    """Test 7: If evidence is genuinely insufficient, do not force resolution; remain EVIDENCE_INSUFFICIENT."""
    from ai.app.evaluation.assessment_cases import make_retrieval_result
    engine = DefaultAssessmentEngine()

    ret_prov = make_retrieval_result(
        provision_id="prov_doc_reg_sebi_test_sec_1",
        provision_text="Brokers shall not levy unauthorised charges.",
        source_class="REGULATORY",
        authority="SEBI",
        temporal_status="CURRENT",
    )

    req = AssessmentRequest(
        case_id="CASE-T7-SAFE",
        case_facts={"organisation": "ORG_ZERODHA"},  # Missing charged_amount and transaction_date
        evidence_items=[],
        retrieval_response=RetrievalResponse(results=[ret_prov], total_candidates_found=1),
        require_regulatory_coverage=True,
    )

    res = engine.assess(req)

    assert res.status == AssessmentStatus.EVIDENCE_INSUFFICIENT
    assert "charged_amount" in res.missing_information
    assert "transaction_date" in res.missing_information


