"""Regulatory Gap Benchmark Cases (L2/L3) for SANGYAN Evaluation (Phase 7A).

Epistemic foundation:
- 5 cases testing boundaries where the subject matter falls outside SEBI/depository jurisdiction
  or represents an unindexed legal regime (Crypto, unregulated algo tips, P2P lending, digital gold).
- Strictly enforces REGULATORY_COVERAGE_UNRESOLVED: system must NOT hallucinate compliance or violation.
"""

from decimal import Decimal

from ai.app.assessment.contracts import AssessmentStatus
from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedAssessment,
    ExpectedFact,
    ExpectedIssue,
)
from ai.evaluation.corpus.taxonomy import (
    AdversarialSubtype,
    CaseCategory,
    CaseVisibility,
    DifficultyLevel,
)

CASES: list[EvaluationCase] = [
    # 1. Spot Cryptocurrency Exchange Dispute
    EvaluationCase(
        case_id="GAP-001",
        title="Dispute over cryptocurrency token withdrawal from unregulated crypto exchange",
        category=CaseCategory.REGULATORY_GAP,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.MISSING_CORPUS_COVERAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="A crypto exchange froze my Bitcoin and Ethereum withdrawals and deducted 5% fees. Can I file a SEBI SCORES complaint to get a refund?",
        expected_facts=[
            ExpectedFact(field="asset_type", expected_value="cryptocurrency", required=True),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Regulatory jurisdiction over spot virtual digital asset (VDA) exchanges",
            secondary_issues=["SEBI statutory scope limitation"],
        ),
        is_blocked_by_corpus_gap=True,
        corpus_gap_reason="Cryptocurrency spot trading platforms are not regulated by SEBI as securities market intermediaries.",
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
            expected_findings=["Cryptocurrency spot platforms do not fall under SEBI jurisdiction; cannot be redressed via SCORES."],
            provenance_notes="SEBI regulates securities and commodities derivatives, not unregulated virtual digital asset spot exchanges.",
        ),
    ),

    # 2. Unregistered Telegram Advisory Tipster
    EvaluationCase(
        case_id="GAP-002",
        title="Grievance against an unregistered Telegram trading tip channel",
        category=CaseCategory.REGULATORY_GAP,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.MISSING_CORPUS_COVERAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="I paid Rs 25,000 subscription to a Telegram group 'BankNifty Jackpot Calls'. All their calls hit stop loss and I lost Rs 2 lakh. Can SEBI recover my subscription?",
        expected_facts=[
            ExpectedFact(field="entity_type", expected_value="unregistered_telegram_channel", required=True),
            ExpectedFact(field="fee_paid", expected_value=Decimal("25000.00"), data_type="DECIMAL"),
        ],
        is_blocked_by_corpus_gap=True,
        corpus_gap_reason="Unregistered individuals operating on messaging platforms without SEBI RA registration.",
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
            expected_findings=["Unregistered advisory services cannot be resolved through standard broker grievance mechanism."],
            provenance_notes="Matter involves unauthorized advisory activity; remedy lies in reporting to SEBI enforcement/police cyber cell.",
        ),
    ),

    # 3. Private Corporate Loan / Unregulated Chit Fund
    EvaluationCase(
        case_id="GAP-003",
        title="Default on private corporate promissory note",
        category=CaseCategory.REGULATORY_GAP,
        difficulty=DifficultyLevel.L2,
        adversarial_subtype=AdversarialSubtype.MISSING_CORPUS_COVERAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="A private local builder took Rs 10 lakh loan from me promising 15% interest and defaulted. Can I file on SCORES?",
        expected_facts=[
            ExpectedFact(field="instrument", expected_value="private_loan", required=True),
        ],
        is_blocked_by_corpus_gap=True,
        corpus_gap_reason="Private civil debt agreements do not constitute exchange-traded securities under SEBI Act.",
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
            expected_findings=["Private loan disputes are outside securities market regulatory purview."],
        ),
    ),

    # 4. Digital Gold Leasing App
    EvaluationCase(
        case_id="GAP-004",
        title="Digital gold leasing app default and fee dispute",
        category=CaseCategory.REGULATORY_GAP,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.MISSING_CORPUS_COVERAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="I leased digital gold on a mobile fintech app. The app shut down operations and my gold is locked. Is this covered by SEBI regulations?",
        expected_facts=[
            ExpectedFact(field="product", expected_value="digital_gold_leasing", required=True),
        ],
        is_blocked_by_corpus_gap=True,
        corpus_gap_reason="Digital gold leasing products are currently unregulated by SEBI or RBI as collective schemes.",
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
            expected_findings=["Digital gold is not a SEBI-regulated security (unlike Sovereign Gold Bonds or Gold ETFs)."],
        ),
    ),

    # 5. Offshore Unregistered Stock App
    EvaluationCase(
        case_id="GAP-005",
        title="Unregulated foreign brokerage fractional shares dispute",
        category=CaseCategory.REGULATORY_GAP,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.MISSING_CORPUS_COVERAGE,
        visibility=CaseVisibility.PUBLIC,
        user_input="An offshore trading app based in Seychelles refused to execute my withdrawal of US tech stock fractions.",
        expected_facts=[
            ExpectedFact(field="jurisdiction", expected_value="offshore_seychelles", required=True),
        ],
        is_blocked_by_corpus_gap=True,
        corpus_gap_reason="Foreign entities operating without domestic SEBI intermediary registration.",
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
            expected_findings=["SEBI jurisdiction extends only to domestic registered intermediaries; offshore platforms are outside SCORES purview."],
        ),
    ),
]
