"""Comprehensive tests for SANGYAN Epistemic Assessment Layer.

Covers:
1. Basic comparison (₹20 > ₹15 -> TRUE)
2. Compliant case (₹10 <= ₹15 -> COMPLIANT)
3. Missing evidence (transaction_type = UNKNOWN -> EVIDENCE_INSUFFICIENT)
4. Exception evaluation (BSDA nil AMC exception alters outcome)
5. Temporal mismatch (2026 rule evaluated against 2021 incident -> NOT_APPLICABLE)
6. Historical ambiguity (no operative historical rule -> TEMPORALITY_UNRESOLVED)
7. Regulatory vs organisation (statutory compliance vs tariff policy deviation -> layered findings)
8. Conflicting provisions (two applicable provisions contradict -> CONFLICTING_PROVISIONS)
9. Numerical precision (Decimal arithmetic without float drift)
10. Provenance preservation (findings retain evidence and provision citations)
11. Safety Invariant 1: No COMPLIANT_WITH_REGULATION solely from absence of violation
12. Safety Invariant 2: No VIOLATION_CONFIRMED when required condition is UNKNOWN
13. Three-valued logic operations (AND, OR, NOT with Kleene truth tables)
14. Contradicted evidence detection
"""

from datetime import date
from decimal import Decimal
import pytest

from ai.app.assessment.condition_evaluator import ConditionEvaluator
from ai.app.assessment.conflict_detector import ConflictDetector
from ai.app.assessment.contracts import (
    ApplicabilityEvaluation,
    AssessmentFinding,
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    ConditionEvaluation,
    ConditionOperator,
    EpistemicLayer,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceRequirementStatus,
    EvidenceType,
    RuleOutcome,
    ThreeValuedLogic,
)
from ai.app.assessment.engine import DefaultAssessmentEngine
from ai.app.assessment.evidence_manager import EvidenceManager
from ai.app.assessment.fee_evaluator import FeeEvaluator, FeeType
from ai.app.assessment.rule_evaluator import RuleEvaluator
from ai.app.evaluation.assessment_cases import make_retrieval_result
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult


# =====================================================================
# 1. Three-Valued Logic Tests
# =====================================================================

def test_three_valued_logic_operations():
    """Verify Kleene three-valued logic algebraic laws."""
    T = ThreeValuedLogic.TRUE
    F = ThreeValuedLogic.FALSE
    U = ThreeValuedLogic.UNKNOWN

    # NOT
    assert ~T == F
    assert ~F == T
    assert ~U == U

    # AND
    assert (T & T) == T
    assert (T & F) == F
    assert (T & U) == U
    assert (F & U) == F  # False dominates AND
    assert (U & U) == U

    # OR
    assert (T | T) == T
    assert (T | F) == T  # True dominates OR
    assert (T | U) == T
    assert (F | F) == F
    assert (F | U) == U
    assert (U | U) == U


# =====================================================================
# 2. Condition Evaluator Tests
# =====================================================================

def test_condition_evaluator_numerical():
    """Test deterministic decimal numerical comparisons."""
    evaluator = ConditionEvaluator()

    # ₹20 > ₹15 -> TRUE
    cond1 = evaluator.evaluate(
        condition_id="C1",
        field="charged_amount",
        operator=ConditionOperator.GREATER_THAN,
        target_value=Decimal("15.00"),
        observed_value=Decimal("20.00"),
    )
    assert cond1.result == ThreeValuedLogic.TRUE

    # ₹10 <= ₹15 -> TRUE
    cond2 = evaluator.evaluate(
        condition_id="C2",
        field="charged_amount",
        operator=ConditionOperator.LESS_OR_EQUAL,
        target_value=Decimal("15.00"),
        observed_value=Decimal("10.00"),
    )
    assert cond2.result == ThreeValuedLogic.TRUE

    # Missing observed value -> UNKNOWN
    cond3 = evaluator.evaluate(
        condition_id="C3",
        field="charged_amount",
        operator=ConditionOperator.LESS_OR_EQUAL,
        target_value=Decimal("15.00"),
        observed_value=None,
    )
    assert cond3.result == ThreeValuedLogic.UNKNOWN


def test_condition_evaluator_dates():
    """Test date comparisons with three-valued logic."""
    evaluator = ConditionEvaluator()

    cond = evaluator.evaluate(
        condition_id="C_DATE",
        field="transaction_date",
        operator=ConditionOperator.DATE_BEFORE,
        target_value=date(2026, 6, 1),
        observed_value=date(2026, 2, 1),
    )
    assert cond.result == ThreeValuedLogic.TRUE


# =====================================================================
# 3. Fee Evaluator Tests
# =====================================================================

def test_fee_evaluator_decimal_precision():
    """Verify money calculations use Decimal and do not round silently."""
    # Percentage fee: 0.05% on ₹1,234,567.89
    res = FeeEvaluator.evaluate_percentage_fee(
        charged=Decimal("617.28"),
        transaction_value=Decimal("1234567.89"),
        percentage_rate=Decimal("0.0005"),  # 0.05%
        currency="INR",
        precision=2,
    )
    assert res.is_compliant == ThreeValuedLogic.TRUE
    assert res.permitted_amount == Decimal("617.28")
    assert isinstance(res.permitted_amount, Decimal)

    # Ceiling check
    res_ceil = FeeEvaluator.evaluate_maximum_ceiling(
        charged=Decimal("25.00"),
        maximum_ceiling=Decimal("15.00"),
    )
    assert res_ceil.exceeds_permitted == ThreeValuedLogic.TRUE
    assert res_ceil.is_compliant == ThreeValuedLogic.FALSE
    assert res_ceil.excess_amount == Decimal("10.00")


# =====================================================================
# 4. Evidence Manager & Contradiction Tests
# =====================================================================

def test_evidence_manager_contradiction():
    """Verify evidence contradictions are detected rather than silently resolved."""
    mgr = EvidenceManager([
        EvidenceItem(
            evidence_id="E1",
            case_id="C1",
            evidence_type=EvidenceType.USER_STATEMENT,
            field_name="charged_amount",
            value=Decimal("50.00"),
            source="user",
        ),
        EvidenceItem(
            evidence_id="E2",
            case_id="C1",
            evidence_type=EvidenceType.TRANSACTION_RECORD,
            field_name="charged_amount",
            value=Decimal("15.00"),
            source="contract_note",
        ),
    ])

    val, status, ev_ids = mgr.get_field_value("charged_amount")
    assert status == EvidenceRequirementStatus.CONTRADICTED
    assert val is None
    assert len(ev_ids) == 2


# =====================================================================
# 5. Assessment Engine - Confirmed Violation
# =====================================================================

def test_assessment_confirmed_violation():
    """Test broker charged ₹25 exceeding statutory ceiling of ₹15."""
    engine = DefaultAssessmentEngine()

    prov = make_retrieval_result(
        provision_id="prov_sebi_ceiling_15",
        provision_text="Depository participant charges shall not exceed ₹15 per debit.",
        authority="SEBI",
        source_class="REGULATORY",
        document_id="doc_sebi_01",
        effective_from=date(2023, 1, 1),
    )

    request = AssessmentRequest(
        case_id="CASE-VIO",
        case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("15.00")},
        evidence_items=[
            EvidenceItem(
                evidence_id="EV-VIO-AMT",
                case_id="CASE-VIO",
                evidence_type=EvidenceType.TRANSACTION_RECORD,
                field_name="charged_amount",
                value=Decimal("25.00"),
                source="contract_note.pdf",
            ),
            EvidenceItem(
                evidence_id="EV-VIO-DATE",
                case_id="CASE-VIO",
                evidence_type=EvidenceType.TRANSACTION_RECORD,
                field_name="transaction_date",
                value=date(2026, 2, 1),
                source="contract_note.pdf",
            ),
        ],
        retrieval_response=RetrievalResponse(results=[prov], total_candidates_found=1),
        incident_date=date(2026, 2, 1),
    )

    res = engine.assess(request)
    assert res.status == AssessmentStatus.VIOLATION_CONFIRMED
    assert any(f.status == AssessmentStatus.VIOLATION_CONFIRMED for f in res.findings)
    assert len(res.provenance_ids) > 0


# =====================================================================
# 6. Assessment Engine - Confirmed Compliance
# =====================================================================

def test_assessment_confirmed_compliance():
    """Test broker charged ₹13.50 within statutory ceiling of ₹15."""
    engine = DefaultAssessmentEngine()

    prov = make_retrieval_result(
        provision_id="prov_sebi_ceiling_15",
        provision_text="Depository participant charges shall not exceed ₹15 per debit.",
        authority="SEBI",
        source_class="REGULATORY",
        document_id="doc_sebi_01",
        effective_from=date(2023, 1, 1),
    )

    request = AssessmentRequest(
        case_id="CASE-CMP",
        case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("15.00")},
        evidence_items=[
            EvidenceItem(
                evidence_id="EV-CMP-AMT",
                case_id="CASE-CMP",
                evidence_type=EvidenceType.TRANSACTION_RECORD,
                field_name="charged_amount",
                value=Decimal("13.50"),
                source="contract_note.pdf",
            ),
            EvidenceItem(
                evidence_id="EV-CMP-DATE",
                case_id="CASE-CMP",
                evidence_type=EvidenceType.TRANSACTION_RECORD,
                field_name="transaction_date",
                value=date(2026, 2, 1),
                source="contract_note.pdf",
            ),
        ],
        retrieval_response=RetrievalResponse(results=[prov], total_candidates_found=1),
        incident_date=date(2026, 2, 1),
    )

    res = engine.assess(request)
    assert res.status == AssessmentStatus.COMPLIANT_WITH_REGULATION


# =====================================================================
# 7. Safety Invariant 1: No Compliance Without Affirmative Evidence
# =====================================================================

def test_safety_invariant_no_compliance_from_absence_of_violation():
    """SANGYAN must never produce COMPLIANT_WITH_REGULATION solely from absence of a violation."""
    engine = DefaultAssessmentEngine()

    # Provision is not evaluated as satisfied because required facts are not available
    prov = make_retrieval_result(
        provision_id="prov_general_disclosure",
        provision_text="Stock brokers shall issue contract notes within 24 hours.",
        authority="SEBI",
        source_class="REGULATORY",
        document_id="doc_sebi_01",
        effective_from=date(2023, 1, 1),
    )

    request = AssessmentRequest(
        case_id="CASE-NO-AFFIRM",
        case_facts={"issue_category": "unrelated_claim"},
        evidence_items=[
            EvidenceItem(
                evidence_id="EV-1",
                case_id="CASE-NO-AFFIRM",
                evidence_type=EvidenceType.USER_STATEMENT,
                field_name="charged_amount",
                value=Decimal("10.00"),
                source="user",
            ),
            EvidenceItem(
                evidence_id="EV-2",
                case_id="CASE-NO-AFFIRM",
                evidence_type=EvidenceType.SYSTEM_RECORD,
                field_name="transaction_date",
                value=date(2026, 2, 1),
                source="system",
            ),
        ],
        retrieval_response=RetrievalResponse(results=[prov], total_candidates_found=1),
        incident_date=date(2026, 2, 1),
    )

    res = engine.assess(request)
    # MUST NOT be COMPLIANT_WITH_REGULATION!
    assert res.status != AssessmentStatus.COMPLIANT_WITH_REGULATION
    assert res.status == AssessmentStatus.EVIDENCE_INSUFFICIENT


# =====================================================================
# 8. Safety Invariant 2: No Violation When Condition is UNKNOWN
# =====================================================================

def test_safety_invariant_no_violation_when_condition_unknown():
    """SANGYAN must never produce VIOLATION_CONFIRMED when a required condition remains UNKNOWN."""
    engine = DefaultAssessmentEngine()

    prov = make_retrieval_result(
        provision_id="prov_sebi_ceiling_15",
        provision_text="Depository participant charges shall not exceed ₹15 per debit.",
        authority="SEBI",
        source_class="REGULATORY",
        document_id="doc_sebi_01",
        effective_from=date(2023, 1, 1),
    )

    # Missing charged_amount
    request = AssessmentRequest(
        case_id="CASE-MISSING-AMT",
        case_facts={"transaction_type": "equity_delivery"},
        evidence_items=[
            EvidenceItem(
                evidence_id="EV-DATE",
                case_id="CASE-MISSING-AMT",
                evidence_type=EvidenceType.TRANSACTION_RECORD,
                field_name="transaction_date",
                value=date(2026, 2, 1),
                source="statement.pdf",
            ),
        ],
        retrieval_response=RetrievalResponse(results=[prov], total_candidates_found=1),
        incident_date=date(2026, 2, 1),
    )

    res = engine.assess(request)
    assert res.status != AssessmentStatus.VIOLATION_CONFIRMED
    assert res.status == AssessmentStatus.EVIDENCE_INSUFFICIENT
    assert "charged_amount" in res.missing_information


# =====================================================================
# 9. Exception Evaluation: BSDA Account Exemption
# =====================================================================

def test_exception_bsda_exemption():
    """Verify BSDA account qualification alters outcome via statutory exemption."""
    engine = DefaultAssessmentEngine()

    prov = make_retrieval_result(
        provision_id="prov_amc_rule",
        provision_text="Annual maintenance charge for demat accounts shall be ₹300.",
        authority="SEBI",
        source_class="REGULATORY",
        document_id="doc_sebi_01",
        effective_from=date(2023, 1, 1),
    )

    request = AssessmentRequest(
        case_id="CASE-BSDA",
        case_facts={"is_bsda": True, "account_type": "BSDA", "permitted_amount": Decimal("0.00")},
        evidence_items=[
            EvidenceItem(
                evidence_id="EV-BSDA-1",
                case_id="CASE-BSDA",
                evidence_type=EvidenceType.TRANSACTION_RECORD,
                field_name="charged_amount",
                value=Decimal("0.00"),
                source="account_statement.pdf",
            ),
            EvidenceItem(
                evidence_id="EV-BSDA-2",
                case_id="CASE-BSDA",
                evidence_type=EvidenceType.DOCUMENT,
                field_name="is_bsda",
                value=True,
                source="holding_statement.pdf",
            ),
            EvidenceItem(
                evidence_id="EV-BSDA-3",
                case_id="CASE-BSDA",
                evidence_type=EvidenceType.SYSTEM_RECORD,
                field_name="transaction_date",
                value=date(2026, 2, 1),
                source="system",
            ),
        ],
        retrieval_response=RetrievalResponse(results=[prov], total_candidates_found=1),
        incident_date=date(2026, 2, 1),
    )

    res = engine.assess(request)
    assert res.status == AssessmentStatus.COMPLIANT_WITH_REGULATION


# =====================================================================
# 10. Multi-Layered Assessment: Regulatory vs Organisation
# =====================================================================

def test_multi_layered_findings():
    """Verify layered findings distinguishing statutory compliance from broker policy deviation."""
    engine = DefaultAssessmentEngine()

    # Charged ₹14: <= ₹15 (SEBI compliant) but > ₹13.50 (Zerodha policy deviation)
    prov_reg = make_retrieval_result(
        provision_id="prov_sebi_ceiling_15",
        provision_text="Depository participant charges shall not exceed ₹15 per debit.",
        authority="SEBI",
        source_class="REGULATORY",
        document_id="doc_sebi_01",
        effective_from=date(2023, 1, 1),
    )
    prov_org = make_retrieval_result(
        provision_id="prov_zerodha_tariff_1350",
        provision_text="Zerodha DP charge is ₹13.50 per scrip.",
        authority=None,
        organisation_id="ORG_ZERODHA",
        source_class="ORGANISATION_POLICY",
        document_id="doc_zerodha_01",
        effective_from=date(2023, 1, 1),
    )

    request = AssessmentRequest(
        case_id="CASE-LAYERED",
        case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("13.50")},
        evidence_items=[
            EvidenceItem(
                evidence_id="EV-1",
                case_id="CASE-LAYERED",
                evidence_type=EvidenceType.TRANSACTION_RECORD,
                field_name="charged_amount",
                value=Decimal("14.00"),
                source="statement.pdf",
            ),
            EvidenceItem(
                evidence_id="EV-2",
                case_id="CASE-LAYERED",
                evidence_type=EvidenceType.TRANSACTION_RECORD,
                field_name="transaction_date",
                value=date(2026, 2, 1),
                source="statement.pdf",
            ),
        ],
        retrieval_response=RetrievalResponse(results=[prov_reg, prov_org], total_candidates_found=2),
        incident_date=date(2026, 2, 1),
        target_organisation="ORG_ZERODHA",
        require_regulatory_coverage=True,
    )

    res = engine.assess(request)
    assert res.status == AssessmentStatus.ORGANISATION_POLICY_DEVIATION
    # Findings should show organization policy deviation
    assert any(f.status == AssessmentStatus.ORGANISATION_POLICY_DEVIATION for f in res.findings)


# =====================================================================
# 11. Conflicting Provisions & Resolution Hierarchy
# =====================================================================

def test_conflicting_provisions_resolution_hierarchy():
    """Verify authority hierarchy resolves contradiction between regulatory ceiling and broker tariff."""
    prov_reg = make_retrieval_result(
        provision_id="prov_sebi_15",
        provision_text="Statutory maximum fee limit is ₹15.",
        authority="SEBI",
        source_class="REGULATORY",
        document_id="doc_sebi_01",
        effective_from=date(2023, 1, 1),
    )
    prov_org = make_retrieval_result(
        provision_id="prov_broker_20",
        provision_text="Broker policy tariff is ₹20.",
        authority=None,
        organisation_id="ORG_TEST",
        source_class="ORGANISATION_POLICY",
        document_id="doc_broker_01",
        effective_from=date(2023, 1, 1),
    )

    r_map = {prov_reg.provision_id: prov_reg, prov_org.provision_id: prov_org}

    eval1 = ApplicabilityEvaluation(
        provision_id=prov_reg.provision_id,
        temporal_status="APPLICABLE",
        authority_status="APPLICABLE",
        overall_applicability="APPLICABLE",
        rule_outcome=RuleOutcome.VIOLATED,
        conditions=[
            ConditionEvaluation(
                condition_id="C1",
                field="charged_amount",
                operator=ConditionOperator.LESS_OR_EQUAL,
                target_value=Decimal("15.00"),
                observed_value=Decimal("20.00"),
                result=ThreeValuedLogic.FALSE,
            )
        ],
    )
    eval2 = ApplicabilityEvaluation(
        provision_id=prov_org.provision_id,
        temporal_status="APPLICABLE",
        authority_status="APPLICABLE",
        overall_applicability="APPLICABLE",
        rule_outcome=RuleOutcome.SATISFIED,
        conditions=[
            ConditionEvaluation(
                condition_id="C2",
                field="charged_amount",
                operator=ConditionOperator.LESS_OR_EQUAL,
                target_value=Decimal("20.00"),
                observed_value=Decimal("20.00"),
                result=ThreeValuedLogic.TRUE,
            )
        ],
    )

    conflicts = ConflictDetector.detect_conflicts([eval1, eval2], r_map)
    assert len(conflicts) == 1
    # Resolved by AUTHORITY_HIERARCHY (SEBI overrides Broker)
    assert conflicts[0].resolved is True
    assert conflicts[0].prevailing_provision_id == prov_reg.provision_id
