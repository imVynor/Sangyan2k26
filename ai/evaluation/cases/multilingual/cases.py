"""Multilingual Benchmark Cases (L1/L2) for SANGYAN Evaluation (Phase 7A).

Epistemic foundation:
- 5 authentic Hindi and Hinglish investor grievance cases.
- Evaluates fact invariance, issue invariance, retrieval invariance, and deterministic assessment invariance.
- Verifies that colloquial expressions map to the identical underlying canonical case state.
"""

from decimal import Decimal

from ai.app.assessment.contracts import AssessmentStatus
from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedAssessment,
    ExpectedFact,
    ExpectedIssue,
    ExpectedProvision,
)
from ai.evaluation.corpus.taxonomy import (
    CaseCategory,
    CaseVisibility,
    DifficultyLevel,
    RetrievalRelevance,
)

CASES: list[EvaluationCase] = [
    # 1. Hinglish: Zerodha DP Charge Debit
    EvaluationCase(
        case_id="MULTI-001",
        title="Hinglish delivery sell DP charge inquiry against Zerodha",
        category=CaseCategory.MULTILINGUAL,
        difficulty=DifficultyLevel.L1,
        language="hinglish",
        visibility=CaseVisibility.PUBLIC,
        user_input="Zerodha ne mere account se 15.93 rupaye kat liye jab maine Tata Motors ke share beche the. Delivery pe to brokerage zero bola tha na, fir ye paise kyu kate?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("15.93"), data_type="DECIMAL"),
            ExpectedFact(field="transaction_type", expected_value="equity_delivery_sell", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Depository Participant (DP) charge debit on equity delivery sell",
            secondary_issues=["Brokerage fee transparency"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_9_957d01daca9b",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Zerodha tariff establishes Rs 13.50 + 18% GST (Rs 15.93) per scrip on equity delivery debit.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Deduction of Rs 15.93 is the standard DP debit charge, distinct from zero delivery brokerage."],
        ),
    ),

    # 2. Hindi Devanagari: Angel One Demat AMC Debit
    EvaluationCase(
        case_id="MULTI-002",
        title="Hindi inquiry on Angel One annual maintenance charges",
        category=CaseCategory.MULTILINGUAL,
        difficulty=DifficultyLevel.L1,
        language="hi",
        visibility=CaseVisibility.PUBLIC,
        user_input="एंजेल वन ने बिना किसी पूर्व सूचना के मेरे डीमैट खाते से 300 रुपये एएमसी शुल्क काट लिया है। क्या ब्रोकर ऐसा कर सकता है?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ANGELONE", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("300.00"), data_type="DECIMAL"),
            ExpectedFact(field="fee_type", expected_value="annual_maintenance_charge", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Angel One Demat Annual Maintenance Charges (AMC)",
            secondary_issues=["Account fee transparency"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_angelone_e6c7f9c9c4341582_sec_1_0d44ed915294",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Angel One tariff schedule specifies regular annual maintenance charges.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["AMC deduction of Rs 300 conforms with agreed client tariff schedule."],
        ),
    ),

    # 3. Hinglish: Groww Negative Balance Dispute
    EvaluationCase(
        case_id="MULTI-003",
        title="Hinglish Groww negative ledger balance inquiry",
        category=CaseCategory.MULTILINGUAL,
        difficulty=DifficultyLevel.L2,
        language="hinglish",
        visibility=CaseVisibility.PUBLIC,
        user_input="Bhai Groww pe account kholne ka charge zero tha par mere ledger me 50 rupaye negative balance kyu dikha raha hai?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_GROWW", required=True),
            ExpectedFact(field="negative_amount", expected_value=Decimal("50.00"), data_type="DECIMAL"),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Groww negative ledger balance inquiry",
            secondary_issues=["Account opening transparency"],
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Ledger statement required to ascertain cause of Rs 50 debit."],
        ),
    ),

    # 4. Hindi Devanagari: SEBI SCORES Timeline Violation
    EvaluationCase(
        case_id="MULTI-004",
        title="Hindi grievance regarding SCORES 30-day resolution timeline breach",
        category=CaseCategory.MULTILINGUAL,
        difficulty=DifficultyLevel.L1,
        language="hi",
        visibility=CaseVisibility.PUBLIC,
        user_input="मैंने सेबी स्कोर्स पोर्टल पर 45 दिन पहले अपने दलाल के खिलाफ शिकायत दर्ज की थी, लेकिन अभी तक कोई समाधान नहीं मिला।",
        expected_facts=[
            ExpectedFact(field="elapsed_days", expected_value=45, data_type="INTEGER"),
            ExpectedFact(field="portal", expected_value="SEBI_SCORES", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="SEBI SCORES 30-day grievance redressal statutory timeline",
            secondary_issues=["Entity non-compliance escalation"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_page_15_2a0bf157af2e",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI Master Circular mandates intermediaries resolve investor grievances within 30 calendar days.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["Broker exceeded statutory timeline to redress complaint on SCORES."],
            expected_violations=["Violation of SEBI investor grievance timeline guidelines."],
        ),
    ),

    # 5. Hinglish: Upstox Intraday Brokerage Ceiling
    EvaluationCase(
        case_id="MULTI-005",
        title="Hinglish Upstox intraday brokerage rate inquiry",
        category=CaseCategory.MULTILINGUAL,
        difficulty=DifficultyLevel.L1,
        language="hinglish",
        visibility=CaseVisibility.PUBLIC,
        user_input="Upstox me maine 1 lakh ka intraday buy kiya tha aur 20 rupaye brokerage laga. Kya 20 rupaye sahi charge hai?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_UPSTOX", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("20.00"), data_type="DECIMAL"),
            ExpectedFact(field="transaction_type", expected_value="intraday_equity", required=True),
            ExpectedFact(field="order_value", expected_value=Decimal("100000.00"), data_type="DECIMAL"),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Upstox equity intraday brokerage tariff cap (Rs 20)",
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_upstox_f2afe8afaaac8c78_sec_17_a667135eb1c5",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Upstox charges Rs 20 or 0.05% whichever is lower on intraday trades.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Intraday brokerage capped at Rs 20 complies with published tariff."],
        ),
    ),
]
