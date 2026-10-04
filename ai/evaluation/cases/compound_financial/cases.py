"""Compound Financial Benchmark Cases (L5) for SANGYAN Evaluation (Phase 7A).

Epistemic foundation:
- 10 fine-grained multi-component financial calculation cases.
- Uses exact Decimal arithmetic throughout (STT, GST, Exchange Txn Charges, SEBI fees, Stamp Duty, DP charges).
- Explicitly tests and classifies compound error types: TAX_INCORRECT, COMPONENT_MISSING, COMPONENT_DUPLICATED, etc.
"""

from decimal import Decimal

from ai.app.assessment.contracts import AssessmentStatus
from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedAssessment,
    ExpectedFact,
    ExpectedFinancialBreakdown,
    ExpectedIssue,
    ExpectedProvision,
)
from ai.evaluation.corpus.taxonomy import (
    AdversarialSubtype,
    CaseCategory,
    CaseVisibility,
    CompoundErrorType,
    DifficultyLevel,
    RetrievalRelevance,
)

CASES: list[EvaluationCase] = [
    # 1. Delivery Sell Complete Breakdown (₹10,000 turnover)
    EvaluationCase(
        case_id="COMP-001",
        title="Complete delivery sell statutory and depository fee breakdown",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="I sold shares worth Rs 10,000 on Zerodha. My contract note shows total deductions of Rs 26.35. Is this mathematical breakdown exact?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="turnover", expected_value=Decimal("10000.00"), data_type="DECIMAL"),
            ExpectedFact(field="total_deductions", expected_value=Decimal("26.35"), data_type="DECIMAL"),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            base_amount=Decimal("10000.00"),
            brokerage=Decimal("0.00"),
            stt=Decimal("10.00"),                     # 0.1% on delivery sell
            exchange_txn_charge=Decimal("0.35"),     # 0.00345% on NSE
            sebi_turnover_fee=Decimal("0.01"),       # 0.0001%
            stamp_duty=Decimal("0.00"),              # 0 on sell
            gst=Decimal("0.06"),                     # 18% of (brokerage 0 + txn 0.35) = 0.063 -> 0.06
            dp_charges=Decimal("15.93"),              # 13.50 + 18% GST (2.43)
            total_expected=Decimal("26.35"),
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["All 7 statutory and depository components reconcile exactly to Rs 26.35."],
        ),
    ),

    # 2. Tax Incorrect Trap: GST Charged on STT
    EvaluationCase(
        case_id="COMP-002",
        title="Unlawful GST levy on STT and Stamp Duty (Tax-on-Tax trap)",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="Broker calculated 18% GST not just on brokerage and transaction fees, but also added STT and Stamp duty into the taxable value. Is this lawful?",
        expected_facts=[
            ExpectedFact(field="taxable_base_inflated", expected_value=True, data_type="BOOLEAN"),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            known_error_trap=CompoundErrorType.TAX_INCORRECT,
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_angelone_e6c7f9c9c4341582_sec_4_bc51f4f15524",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Statutory fee schedule specifies GST at 18% applies only to brokerage and transaction fees, not STT/Stamp Duty.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["GST cannot be levied on statutory taxes (STT and Stamp Duty). GST applies strictly to services (brokerage + exchange charges)."],
            expected_violations=["Violation of GST Act and SEBI fee circulars by levying GST on statutory tax components."],
        ),
    ),

    # 3. Intraday Equity Cap Breakdown (₹2,00,000 turnover)
    EvaluationCase(
        case_id="COMP-003",
        title="Intraday equity turnover with capped brokerage breakdown",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="On an intraday buy order of Rs 2,00,000, Zerodha charged Rs 20 brokerage, Rs 6.90 exchange txn charge, Rs 0.02 SEBI fee, Rs 6.00 stamp duty, and Rs 4.84 GST. Total: Rs 37.76.",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="turnover", expected_value=Decimal("200000.00"), data_type="DECIMAL"),
            ExpectedFact(field="total_charges", expected_value=Decimal("37.76"), data_type="DECIMAL"),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            base_amount=Decimal("200000.00"),
            brokerage=Decimal("20.00"),               # Capped at Rs 20 (0.03% of 2L is 60)
            exchange_txn_charge=Decimal("6.90"),     # 0.00345% of 2,00,000
            sebi_turnover_fee=Decimal("0.02"),       # 0.0001% of 2,00,000
            stamp_duty=Decimal("6.00"),              # 0.003% on buy
            gst=Decimal("4.84"),                     # 18% of (20.00 + 6.90) = 4.842 -> 4.84
            total_expected=Decimal("37.76"),
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Arithmetic breakdown reconciles perfectly to Rs 37.76."],
        ),
    ),

    # 4. Stamp Duty on Delivery Buy vs Sell
    EvaluationCase(
        case_id="COMP-004",
        title="Stamp duty applicability on buy vs sell transactions",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="Why did broker charge Stamp Duty on my share purchase but not on my share sale?",
        expected_facts=[
            ExpectedFact(field="instrument", expected_value="equity_cash", required=True),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            known_error_trap=CompoundErrorType.WRONG_APPLICABILITY,
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Under the Indian Stamp Act, stamp duty on delivery equity is levied exclusively on the buyer (0.015%), not the seller."],
        ),
    ),

    # 5. Duplicate DP Charge Trap
    EvaluationCase(
        case_id="COMP-005",
        title="Duplicate DP charge on single scrip multi-order execution",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="I sold 100 shares of Infosys in two separate sell orders on the same day. Broker debited DP charge of Rs 15.93 twice (Total Rs 31.86). Is this allowed?",
        expected_facts=[
            ExpectedFact(field="charged_amount", expected_value=Decimal("31.86"), data_type="DECIMAL"),
            ExpectedFact(field="scrip_count", expected_value=1, data_type="INTEGER"),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            dp_charges=Decimal("31.86"),
            known_error_trap=CompoundErrorType.COMPONENT_DUPLICATED,
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_9_957d01daca9b",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Depository tariff rules specify DP debit charges are per scrip (ISIN) per day, prohibiting duplicate debit.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["DP charges are levied per scrip per day irrespective of number of executed orders. Levying twice is a duplicate charge violation."],
            expected_violations=["Improper duplicate debit of Depository Participant charge for the same ISIN on the same settlement day."],
        ),
    ),

    # 6. SEBI Turnover Fee Rounding Error Trap
    EvaluationCase(
        case_id="COMP-006",
        title="SEBI turnover fee micro-rounding verification",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="On a trade of Rs 1,00,000, broker charged SEBI turnover fee of Rs 1.00 instead of Rs 0.0001.",
        expected_facts=[
            ExpectedFact(field="order_value", expected_value=Decimal("1000.00"), data_type="DECIMAL"),
            ExpectedFact(field="sebi_fee_billed", expected_value=Decimal("1.00"), data_type="DECIMAL"),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            sebi_turnover_fee=Decimal("1.00"),
            known_error_trap=CompoundErrorType.ROUNDING_ERROR,
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_page_18_8cf99e05aec0",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI turnover fees are Rs 10 per crore (0.0001%), prohibiting rounding up fractional paisa to whole rupees.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["SEBI fee on Rs 1,000 is Rs 0.001 (fractional paisa). Rounding up to Rs 1.00 represents a 1000x overcharge."],
            expected_violations=["Gross mathematical rounding error on regulatory turnover fee."],
        ),
    ),

    # 7. Futures Contract Note Complete Breakdown
    EvaluationCase(
        case_id="COMP-007",
        title="Equity Futures trade statutory charges breakdown",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="On selling 1 lot of Nifty Futures worth Rs 10,00,000, what are the exact statutory charges?",
        expected_facts=[
            ExpectedFact(field="turnover", expected_value=Decimal("1000000.00"), data_type="DECIMAL"),
            ExpectedFact(field="segment", expected_value="futures", required=True),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            base_amount=Decimal("1000000.00"),
            brokerage=Decimal("20.00"),
            stt=Decimal("200.00"),                    # 0.02% on futures sell
            exchange_txn_charge=Decimal("19.00"),     # 0.0019%
            sebi_turnover_fee=Decimal("0.10"),       # 0.0001%
            gst=Decimal("7.04"),                     # 18% of (20.00 + 19.00) = 7.02
            total_expected=Decimal("246.14"),
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Statutory breakdown for Futures sale conforms with SEBI and Exchange specifications."],
        ),
    ),

    # 8. Options Premium STT Breakdown
    EvaluationCase(
        case_id="COMP-008",
        title="Equity Options trade STT on premium breakdown",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="I sold options with total premium value of Rs 50,000. Broker deducted STT of Rs 50. Is STT calculated on premium or strike price?",
        expected_facts=[
            ExpectedFact(field="premium_value", expected_value=Decimal("50000.00"), data_type="DECIMAL"),
            ExpectedFact(field="stt_billed", expected_value=Decimal("50.00"), data_type="DECIMAL"),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            stt=Decimal("50.00"),                    # 0.1% on premium sold
            total_expected=Decimal("50.00"),
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["STT is levied exclusively on the option premium value (0.1% of Rs 50,000 = Rs 50.00), not the notional strike value."],
        ),
    ),

    # 9. Call & Trade Fee Plus GST Breakdown
    EvaluationCase(
        case_id="COMP-009",
        title="Call and trade service fee arithmetic breakdown (₹50 + 18% GST)",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="ICICI Direct billed Rs 59.00 on my ledger after a phone trade. They said Rs 50 was fee and Rs 9 was tax.",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ICICIDIRECT", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("59.00"), data_type="DECIMAL"),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            base_amount=Decimal("50.00"),
            gst=Decimal("9.00"),                     # 18% of 50.00
            total_expected=Decimal("59.00"),
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Rs 50 base fee + 18% GST (Rs 9.00) equals Rs 59.00 exact."],
        ),
    ),

    # 10. Base Amount Discrepancy Trap
    EvaluationCase(
        case_id="COMP-010",
        title="Brokerage computed on placed order quantity instead of executed fill quantity",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.COMPOUND_FEE_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="I placed order for 1,000 shares but only 100 shares were filled before cancellation. Broker computed full percentage brokerage on 1,000 shares value.",
        expected_facts=[
            ExpectedFact(field="filled_quantity", expected_value=100, data_type="INTEGER"),
            ExpectedFact(field="placed_quantity", expected_value=1000, data_type="INTEGER"),
        ],
        expected_financial=ExpectedFinancialBreakdown(
            known_error_trap=CompoundErrorType.BASE_AMOUNT_INCORRECT,
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_5_c63583322bf8",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI broker regulations mandate brokerage be charged only on executed order fills, not placed/cancelled orders.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["Brokerage and transaction charges can only be levied on executed trades, never on unfilled or cancelled order quantities."],
            expected_violations=["Overcharge due to improper calculation base amount on unexecuted order portion."],
        ),
    ),
]
