"""Straightforward Benchmark Cases (L1) for SANGYAN Evaluation (Phase 7A).

Epistemic foundation:
- 15 straightforward grievances with clear facts, single governing provisions,
  and unambiguous expected assessments.
- Real provision IDs matching PostgreSQL knowledge records.
"""

from datetime import date
from decimal import Decimal

from ai.app.assessment.contracts import AssessmentStatus
from ai.app.extraction.contracts import FactEpistemicStatus
from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedAssessment,
    ExpectedFact,
    ExpectedIssue,
    ExpectedProvision,
    ExpectedUnknown,
)
from ai.evaluation.corpus.taxonomy import (
    CaseCategory,
    CaseVisibility,
    DifficultyLevel,
    RetrievalRelevance,
)

CASES: list[EvaluationCase] = [
    # 1. Zerodha DP Charge Dispute
    EvaluationCase(
        case_id="BASIC-001",
        title="Zerodha DP charge debit on equity delivery sale",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="Zerodha deducted Rs 15.93 from my trading ledger on 2026-03-10 after I sold 10 shares of Tata Motors. Why was this fee deducted when equity delivery brokerage is zero?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("15.93"), data_type="DECIMAL", tolerance=Decimal("0.01")),
            ExpectedFact(field="transaction_type", expected_value="equity_delivery_sell", required=True),
            ExpectedFact(field="transaction_date", expected_value=date(2026, 3, 10), data_type="DATE"),
        ],
        expected_unknowns=[
            ExpectedUnknown(field="unauthorized_trade", reason="User explicitly acknowledges selling the shares."),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Depository Participant (DP) charge debit on equity delivery sell",
            secondary_issues=["Brokerage fee transparency"],
            irrelevant_plausible_issues=["Call and trade charges", "Annual maintenance charges"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_9_957d01daca9b",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Zerodha tariff schedule specifies Rs 13.50 + 18% GST (Rs 15.93) per scrip on equity delivery debit.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Charge matches standard DP debit tariff (Rs 13.50 + 18% GST = Rs 15.93)"],
            provenance_notes="Depository debit charge is distinct from brokerage and authorized under CDSL/broker tariff.",
        ),
    ),

    # 2. Angel One DP Charge Dispute
    EvaluationCase(
        case_id="BASIC-002",
        title="Angel One DP charge on share sale",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="Angel One charged me Rs 20 plus GST on 2026-02-15 when I sold my ITC shares. Is this allowed?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ANGELONE", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("20.00"), data_type="DECIMAL", tolerance=Decimal("0.01")),
            ExpectedFact(field="transaction_date", expected_value=date(2026, 2, 15), data_type="DATE"),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Angel One DP charges on debit of shares",
            secondary_issues=["Statutory GST calculation"],
            irrelevant_plausible_issues=["Margin penalty"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_angelone_e6c7f9c9c4341582_sec_28_13f51f8cd117",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Angel One tariff specifies Rs 20 per scrip per day on debit of shares from demat account.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Angel One levies Rs 20 per debit per scrip per day as per published tariff."],
        ),
    ),

    # 3. Groww Account Opening Fee Zero
    EvaluationCase(
        case_id="BASIC-003",
        title="Groww Demat Account opening fee clarification",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="Does Groww charge any fee for opening a new Demat and trading account?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_GROWW", required=True),
            ExpectedFact(field="process", expected_value="account_opening", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Groww Demat and trading account opening charges",
            secondary_issues=["AMC charges"],
            irrelevant_plausible_issues=["Auto square-off charges"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_groww_2a1d9c223b9d744b_sec_root_2ad8c084fb17",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Groww pricing states Rs 0 account opening and Rs 0 annual maintenance charge.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Groww account opening is Rs 0 (Free)."],
        ),
    ),

    # 4. Upstox Equity Delivery Brokerage
    EvaluationCase(
        case_id="BASIC-004",
        title="Upstox equity delivery brokerage rate",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="Upstox charged me Rs 20 brokerage on an equity delivery buy order worth Rs 5,000 on 2026-01-20. Did they overcharge?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_UPSTOX", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("20.00"), data_type="DECIMAL"),
            ExpectedFact(field="transaction_type", expected_value="equity_delivery_buy", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Upstox equity delivery brokerage tariff applicability",
            secondary_issues=["Brokerage ceiling"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_upstox_f2afe8afaaac8c78_sec_17_a667135eb1c5",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Upstox pricing specifies Rs 20 or 2.5% (whichever is lower) per executed order on equity delivery.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Brokerage of Rs 20 complies with Upstox tariff schedule."],
        ),
    ),

    # 5. ICICI Direct Annual Maintenance Charge
    EvaluationCase(
        case_id="BASIC-005",
        title="ICICI Direct annual maintenance charge debit",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="ICICI Direct deducted Rs 300 plus GST as Demat AMC on 2026-01-05 for my trading account. Is this charge compliant?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ICICIDIRECT", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("300.00"), data_type="DECIMAL"),
            ExpectedFact(field="fee_type", expected_value="annual_maintenance_charge", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="ICICI Direct Demat Annual Maintenance Charges (AMC)",
            secondary_issues=["BSDA account eligibility"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_icicidirect_6976eeb19a00e8e7_page_1_1dec99b4f88d",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="ICICI Direct schedule of charges specifies annual demat maintenance fee for standard accounts.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["AMC of Rs 300 is compliant with standard ICICI Direct tariff agreement."],
        ),
    ),

    # 6. SEBI SCORES Complaint Resolution Timeline
    EvaluationCase(
        case_id="BASIC-006",
        title="SEBI SCORES statutory timeline for grievance resolution",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="I lodged a complaint against my broker on SEBI SCORES 45 days ago and the broker has still not responded or resolved it. Has the broker violated the regulatory timeline?",
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
            expected_findings=["Broker exceeded statutory 30-day timeline to redress SCORES complaint."],
            expected_violations=["Violation of SEBI circular timeline on investor grievance redressal."],
        ),
    ),

    # 7. NSDL Grievance Escalation Procedure
    EvaluationCase(
        case_id="BASIC-007",
        title="NSDL Depository escalation hierarchy",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="How do I escalate my grievance against a depository participant to NSDL?",
        expected_facts=[
            ExpectedFact(field="authority", expected_value="NSDL", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="NSDL grievance redressal escalation process",
            secondary_issues=["Depository participant complaint escalation"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_nsdl_37fc29207b492f5f_sec_3_0c03d9c6a662",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="NSDL specifies complaint registration procedure via online portal or physical submission.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Procedure outlines online filing on NSDL portal after DP level failure."],
        ),
    ),

    # 8. Zerodha Intraday Equity Brokerage Rate
    EvaluationCase(
        case_id="BASIC-008",
        title="Zerodha intraday equity brokerage cap",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="Zerodha charged me Rs 20 on an intraday buy trade of Rs 1,00,000 on 2026-02-10. Is Rs 20 correct?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("20.00"), data_type="DECIMAL"),
            ExpectedFact(field="transaction_type", expected_value="intraday_equity", required=True),
            ExpectedFact(field="order_value", expected_value=Decimal("100000.00"), data_type="DECIMAL"),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Zerodha intraday equity brokerage calculation (Rs 20 or 0.03% cap)",
            secondary_issues=["Turnover charges"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_5_c63583322bf8",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Zerodha charges 0.03% or Rs 20 per executed order, whichever is lower. On Rs 1,00,000, 0.03% is Rs 30, so capped at Rs 20.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Charge capped correctly at Rs 20 since 0.03% (Rs 30) exceeds Rs 20 limit."],
        ),
    ),

    # 9. Angel One Pledge Creation Charges
    EvaluationCase(
        case_id="BASIC-009",
        title="Angel One pledge creation fee",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="Angel One charged Rs 20 plus GST for creating a margin pledge on my shares. Is this tariff authorized?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ANGELONE", required=True),
            ExpectedFact(field="action", expected_value="margin_pledge_creation", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Angel One margin pledge creation charges",
            secondary_issues=["Depository pledge fee component"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_angelone_e6c7f9c9c4341582_sec_4_bc51f4f15524",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Angel One statutory and pledge schedule authorizes Rs 20 per pledge request.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Pledge creation fee of Rs 20 + GST matches published tariff schedule."],
        ),
    ),

    # 10. Demat Statement Delivery Frequency
    EvaluationCase(
        case_id="BASIC-010",
        title="Mandatory periodic demat statement delivery",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="My depository participant has not sent me a statement of holding for over 6 months despite regular transactions. Is this a violation?",
        expected_facts=[
            ExpectedFact(field="elapsed_months", expected_value=6, data_type="INTEGER"),
            ExpectedFact(field="transaction_activity", expected_value=True, data_type="BOOLEAN"),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Mandatory demat transaction and holding statement frequency",
            secondary_issues=["Depository participant compliance obligations"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_cdsl_b78236eb9090bedc_sec_3_a65157b112d7",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI/CDSL guidelines require monthly statements if transactions occurred, and quarterly otherwise.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["Depository Participant failed to provide periodic statement within mandated monthly frequency."],
            expected_violations=["Violation of SEBI DP regulations on regular holding statement issuance."],
        ),
    ),

    # 11. Groww Direct Mutual Fund Brokerage Zero
    EvaluationCase(
        case_id="BASIC-011",
        title="Groww zero commission on direct mutual funds",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="Does Groww charge any transaction fee or commission for investing in Direct Mutual Funds?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_GROWW", required=True),
            ExpectedFact(field="product_type", expected_value="direct_mutual_fund", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Groww direct mutual fund investment commission policy",
            secondary_issues=["Brokerage transparency"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_groww_011e4cd915707471_sec_root_2ad8c084fb17",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Groww policy specifies 0% commission and zero transaction fees on all direct mutual fund investments.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Groww does not charge commission on Direct Mutual Funds (Rs 0)."],
        ),
    ),

    # 12. ICICI Direct Call & Trade Charge
    EvaluationCase(
        case_id="BASIC-012",
        title="ICICI Direct Call and Trade fee per executed order",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="I placed an order over the phone through ICICI Direct customer desk and was billed Rs 50 extra on 2026-02-18. Why was this extra charge levied?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ICICIDIRECT", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("50.00"), data_type="DECIMAL"),
            ExpectedFact(field="order_channel", expected_value="phone_call_and_trade", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="ICICI Direct Call and Trade administrative fee",
            secondary_issues=["Order execution channel charges"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_icicidirect_6976eeb19a00e8e7_page_2_7ce19a8b7a20",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="ICICI Direct tariff permits an additional Call & Trade charge of Rs 50 per executed order placed via dealer.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Call & Trade fee of Rs 50 is explicitly provided in ICICI Direct schedule of charges."],
        ),
    ),

    # 13. Contract Note Delivery Timeline
    EvaluationCase(
        case_id="BASIC-013",
        title="Mandatory 24-hour contract note electronic issuance",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="I executed equity trades on 2026-03-01 but the broker did not send any Electronic Contract Note (ECN) even after 72 hours. Is this a violation?",
        expected_facts=[
            ExpectedFact(field="elapsed_hours", expected_value=72, data_type="INTEGER"),
            ExpectedFact(field="document_requested", expected_value="electronic_contract_note", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="SEBI 24-hour statutory contract note issuance requirement",
            secondary_issues=["Broker operational compliance"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_page_18_b378fcf99c73",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI regulations require stockbrokers to issue contract notes within 24 hours of trade execution.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["Stockbroker failed to issue contract note within statutory 24-hour period."],
            expected_violations=["Violation of SEBI Stock Brokers Regulations on contract note delivery."],
        ),
    ),

    # 14. Angel One MTF Interest Rate Transparency
    EvaluationCase(
        case_id="BASIC-014",
        title="Angel One Margin Trading Facility daily interest rate",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="Angel One charged me interest of 0.049% per day on funded MTF stocks in February 2026. Is this rate permissible?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ANGELONE", required=True),
            ExpectedFact(field="product", expected_value="MTF", required=True),
            ExpectedFact(field="daily_rate", expected_value=Decimal("0.049"), data_type="DECIMAL"),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Angel One MTF interest charges and disclosure",
            secondary_issues=["Annualized percentage rate"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_angelone_e6c7f9c9c4341582_sec_1_0d44ed915294",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Angel One MTF terms disclose interest up to ~18% p.a. (approx 0.049% per day) on outstanding margin balances.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Interest rate charged conforms with agreed MTF facility terms."],
        ),
    ),

    # 15. Zerodha Zero Payment Gateway Surcharge for UPI
    EvaluationCase(
        case_id="BASIC-015",
        title="Zerodha zero charges on fund deposit via UPI",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        visibility=CaseVisibility.PUBLIC,
        user_input="Does Zerodha charge any payment gateway fee when adding funds via UPI?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="payment_mode", expected_value="UPI", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Zerodha payment gateway charges on UPI fund transfers",
            secondary_issues=["Net banking gateway charges"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_9_c117f9d9928f",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Zerodha pricing specifies Rs 0 payment gateway charges for funds added via UPI.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["UPI fund transfers to Zerodha trading account are completely free (Rs 0)."],
        ),
    ),
]
