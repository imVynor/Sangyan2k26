"""Ambiguous Benchmark Cases (L2) for SANGYAN Evaluation (Phase 7A).

Epistemic foundation:
- 10 ambiguous grievances with vague quantities, missing transaction types, and imprecise temporal anchors.
- Strict negative unknowns: enforces hallucination penalty if system invents missing facts.
- Explicit clarification expectations and expected assessment EVIDENCE_INSUFFICIENT.
"""

from decimal import Decimal

from ai.app.assessment.contracts import AssessmentStatus
from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedAssessment,
    ExpectedClarification,
    ExpectedFact,
    ExpectedIssue,
    ExpectedUnknown,
)
from ai.evaluation.corpus.taxonomy import (
    AdversarialSubtype,
    CaseCategory,
    CaseVisibility,
    DifficultyLevel,
)

CASES: list[EvaluationCase] = [
    # 1. Vague Amount and Missing Date
    EvaluationCase(
        case_id="AMB-001",
        title="Vague sell fee grievance without amount or date",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="I was charged a lot of money when I sold my shares through Zerodha last month. This is unfair.",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
        ],
        expected_unknowns=[
            ExpectedUnknown(field="charged_amount", reason="User only stated 'a lot of money' without any specific figure."),
            ExpectedUnknown(field="transaction_date", reason="User only stated 'last month' without exact date."),
            ExpectedUnknown(field="scrip_name", reason="User did not name the security sold."),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Unspecified charges on share sale transaction",
            secondary_issues=["Fee dispute"],
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Grievance lacks exact amount, date, and contract note evidence."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["contract note", "exact amount charged", "transaction date"],
            unnecessary_questions=["mother's maiden name", "bank IFSC code"],
        ),
    ),

    # 2. Approximate Amount
    EvaluationCase(
        case_id="AMB-002",
        title="Approximate deduction without trade details",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="Angel One deducted around Rs 50 extra from my ledger recently. Please help.",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ANGELONE", required=True),
        ],
        expected_unknowns=[
            ExpectedUnknown(field="charged_amount", reason="User stated 'around Rs 50' which is approximate."),
            ExpectedUnknown(field="transaction_type", reason="No transaction type specified."),
            ExpectedUnknown(field="transaction_date", reason="User only stated 'recently'."),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Approximate amount and missing ledger statement prevent definitive determination."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["exact ledger entry amount", "date of deduction"],
        ),
    ),

    # 3. Square-off without margin details
    EvaluationCase(
        case_id="AMB-003",
        title="Unspecified auto square-off complaint",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="The broker squared off my open positions without giving me any prior call or warning.",
        expected_facts=[],
        expected_unknowns=[
            ExpectedUnknown(field="organisation", reason="Broker name not mentioned."),
            ExpectedUnknown(field="margin_shortfall", reason="Shortfall amount and margin status not stated."),
            ExpectedUnknown(field="transaction_date", reason="Date and time of square-off omitted."),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Cannot determine whether square-off was due to intraday cut-off or margin shortfall without broker name and trade logs."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["broker name", "square-off timestamp", "margin call notification"],
        ),
    ),

    # 4. Upstox High Brokerage Without Order Count
    EvaluationCase(
        case_id="AMB-004",
        title="Upstox high brokerage assertion without order count",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="Why did Upstox charge me very high brokerage on my trades yesterday? I thought they were discount brokers.",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_UPSTOX", required=True),
        ],
        expected_unknowns=[
            ExpectedUnknown(field="order_count", reason="Number of executed orders not stated."),
            ExpectedUnknown(field="turnover_value", reason="Total traded turnover not provided."),
            ExpectedUnknown(field="segment", reason="Equity delivery vs F&O vs Intraday not specified."),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Total brokerage depends directly on number of executed orders and segment."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["contract note", "number of executed orders", "trading segment"],
        ),
    ),

    # 5. Hidden Fees Without Identity
    EvaluationCase(
        case_id="AMB-005",
        title="Completely anonymous hidden fee grievance",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="They took hidden fees from my trading account and ruined my profits.",
        expected_facts=[],
        expected_unknowns=[
            ExpectedUnknown(field="organisation", reason="No broker or entity identified."),
            ExpectedUnknown(field="charged_amount", reason="No amount specified."),
            ExpectedUnknown(field="transaction_date", reason="No date specified."),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Anonymous statement with no entity or empirical facts."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["name of stockbroker", "details of disputed fee"],
        ),
    ),

    # 6. Negative Demat Balance
    EvaluationCase(
        case_id="AMB-006",
        title="Negative ledger balance inquiry",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="Groww shows my ledger balance as negative after some transactions last week. How can balance become negative?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_GROWW", required=True),
        ],
        expected_unknowns=[
            ExpectedUnknown(field="exact_balance", reason="Exact negative figure not stated."),
            ExpectedUnknown(field="transaction_type", reason="Nature of transactions unspecified."),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Negative balance can result from AMC, DP debit, delayed settlement, or market loss."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["ledger statement showing debit entries"],
        ),
    ),

    # 7. Unspecified Annual Charges
    EvaluationCase(
        case_id="AMB-007",
        title="Vague annual charge complaint against Zerodha",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="Zerodha deducted annual maintenance fee from my funds. Is my account supposed to have free AMC?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="fee_type", expected_value="annual_maintenance_charge", required=True),
        ],
        expected_unknowns=[
            ExpectedUnknown(field="holding_value", reason="Demat holding value not provided (needed to evaluate BSDA zero-AMC threshold)."),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Eligibility for zero AMC under BSDA depends on whether total demat holding value is below regulatory threshold."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["total demat holding valuation", "account type (Regular vs BSDA)"],
        ),
    ),

    # 8. Order Rejection Mystery
    EvaluationCase(
        case_id="AMB-008",
        title="Unexplained sell order rejection",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="My sell order for shares was rejected by the broker system without any clear explanation.",
        expected_facts=[],
        expected_unknowns=[
            ExpectedUnknown(field="rejection_code", reason="RMS error message not provided."),
            ExpectedUnknown(field="edis_status", reason="EDIS TPIN verification status unknown."),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Order rejection requires inspection of RMS reason (e.g. EDIS TPIN missing, circuit filter, short margin)."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["broker order rejection code or screenshot", "whether CDSL TPIN was authorized"],
        ),
    ),

    # 9. Fund Payout Delay
    EvaluationCase(
        case_id="AMB-009",
        title="Unspecified fund withdrawal delay",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="ICICI Direct is holding my withdrawal money and has not credited it to my bank account.",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ICICIDIRECT", required=True),
        ],
        expected_unknowns=[
            ExpectedUnknown(field="request_timestamp", reason="Time of payout request unknown."),
            ExpectedUnknown(field="unsettled_credits", reason="Whether funds are subject to T+1 settlement hold unknown."),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Payout processing time depends on clearing cut-off and settlement status of recent sales."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["date and time of payout request", "settlement status of underlying trade"],
        ),
    ),

    # 10. Ambiguous SMS Alert
    EvaluationCase(
        case_id="AMB-010",
        title="Inquiry on ambiguous depository debit SMS",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.AMBIGUOUS_LANGUAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="I got an SMS from CDSL saying shares were debited from my account, but I don't remember trading today.",
        expected_facts=[
            ExpectedFact(field="authority", expected_value="CDSL", required=True),
        ],
        expected_unknowns=[
            ExpectedUnknown(field="scrip_name", reason="Specific security debited not mentioned."),
            ExpectedUnknown(field="off_market_transfer", reason="Whether transaction was market delivery or off-market transfer unknown."),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Urgent verification needed to establish whether debit corresponds to earlier trade settlement or unauthorized transfer."],
        ),
        expected_clarifications=ExpectedClarification(
            required_clarifications=["SMS text containing ISIN and quantity", "demat transaction statement"],
        ),
    ),
]
