"""Multi-Turn Evidentiary Dialogue Benchmark Cases (L3/L4) for SANGYAN Evaluation (Phase 7A).

Epistemic foundation:
- 5 multi-turn evaluation cases testing iterative state evolution, clarification, document attachment,
  contradiction detection across turns, and case reopening.
- Enforces state continuity, causal assessment transitions, and clarification round termination.
"""

from decimal import Decimal

from ai.app.assessment.contracts import AssessmentStatus
from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedAssessment,
    ExpectedFact,
    ExpectedIssue,
    ExpectedProvision,
    MultiTurnTurn,
)
from ai.evaluation.corpus.taxonomy import (
    CaseCategory,
    CaseVisibility,
    DifficultyLevel,
    RetrievalRelevance,
)

CASES: list[EvaluationCase] = [
    # 1. 3-Turn Clean Resolution Flow
    EvaluationCase(
        case_id="TURN-001",
        title="Sequential resolution of delivery fee dispute across 3 conversational turns",
        category=CaseCategory.MULTI_TURN,
        difficulty=DifficultyLevel.L3,
        visibility=CaseVisibility.PUBLIC,
        user_input="Zerodha deducted Rs 15.93 from my account. Why?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("15.93"), data_type="DECIMAL"),
        ],
        multi_turn_flow=[
            MultiTurnTurn(
                turn_index=1,
                user_message="Zerodha deducted Rs 15.93 from my account. Why?",
                expected_status_after_turn=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                expected_clarifications_asked=["transaction_type", "whether shares were sold"],
            ),
            MultiTurnTurn(
                turn_index=2,
                user_message="I sold 10 shares of Tata Motors from my demat account.",
                expected_status_after_turn=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                expected_facts_delta={"transaction_type": "equity_delivery_sell", "scrip": "Tata Motors"},
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Charge of Rs 15.93 is the standard DP debit charge on equity delivery sell."],
        ),
    ),

    # 2. Clarification then Contradictory Document Upload
    EvaluationCase(
        case_id="TURN-002",
        title="Multi-turn contradiction emergence upon contract note attachment",
        category=CaseCategory.MULTI_TURN,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="My broker charged me Rs 100 brokerage on delivery trades.",
        multi_turn_flow=[
            MultiTurnTurn(
                turn_index=1,
                user_message="My broker charged me Rs 100 brokerage on delivery trades.",
                expected_status_after_turn=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                expected_clarifications_asked=["broker name", "contract note"],
            ),
            MultiTurnTurn(
                turn_index=2,
                user_message="Broker is Zerodha and here is my contract note.",
                attached_documents=[
                    {
                        "document_id": "cn_turn_002.pdf",
                        "content": "Zerodha Broking. Brokerage: Rs 0.00. Exchange Txn Charge: Rs 0.15. DP Charge: Rs 13.50. Total: Rs 15.93.",
                    }
                ],
                expected_status_after_turn=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                expected_facts_delta={"organisation": "ORG_ZERODHA", "charged_amount": Decimal("15.93")},
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Contract note disproves Rs 100 brokerage claim; actual fee was Rs 15.93."],
        ),
    ),

    # 3. User Declines Clarification -> Closed Insufficient
    EvaluationCase(
        case_id="TURN-003",
        title="User declines to provide contract note leading to graceful termination",
        category=CaseCategory.MULTI_TURN,
        difficulty=DifficultyLevel.L3,
        visibility=CaseVisibility.PUBLIC,
        user_input="Angel One overcharged me on trades last week.",
        multi_turn_flow=[
            MultiTurnTurn(
                turn_index=1,
                user_message="Angel One overcharged me on trades last week.",
                expected_status_after_turn=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                expected_clarifications_asked=["contract note"],
            ),
            MultiTurnTurn(
                turn_index=2,
                user_message="I don't have the contract note and I refuse to upload any documents.",
                expected_status_after_turn=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=["Case closed due to lack of verifiable evidence following user decline."],
        ),
    ),

    # 4. Resolved Case Reopened on New Violation Evidence
    EvaluationCase(
        case_id="TURN-004",
        title="Case reopening from compliant to violation confirmed upon new ledger proof",
        category=CaseCategory.MULTI_TURN,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="Angel One charged Rs 20 DP fee which I understand is normal.",
        multi_turn_flow=[
            MultiTurnTurn(
                turn_index=1,
                user_message="Angel One charged Rs 20 DP fee on 2026-02-10.",
                expected_status_after_turn=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            ),
            MultiTurnTurn(
                turn_index=2,
                user_message="Wait, I just noticed they also deducted an unauthorized Rs 500 'Advisory Fee' on the same day without consent.",
                expected_status_after_turn=AssessmentStatus.VIOLATION_CONFIRMED,
                expected_facts_delta={"unauthorized_fee": Decimal("500.00")},
            ),
        ],
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_angelone_e6c7f9c9c4341582_sec_4_bc51f4f15524",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI stockbroker code of conduct prohibits levying unauthorized non-tariff advisory fees without client consent.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["Broker levied unauthorized Rs 500 fee without prior client agreement."],
            expected_violations=["Violation of SEBI code of conduct on unauthorized fee deductions."],
        ),
    ),

    # 5. Multi-Turn BSDA Threshold Reconciliation
    EvaluationCase(
        case_id="TURN-005",
        title="Iterative BSDA eligibility reconciliation across turns",
        category=CaseCategory.MULTI_TURN,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="ICICI Direct charged me AMC on my BSDA account.",
        multi_turn_flow=[
            MultiTurnTurn(
                turn_index=1,
                user_message="ICICI Direct charged me AMC on my BSDA account.",
                expected_status_after_turn=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                expected_clarifications_asked=["portfolio holding valuation"],
            ),
            MultiTurnTurn(
                turn_index=2,
                user_message="Here is my depository holding statement as of billing date.",
                attached_documents=[
                    {
                        "document_id": "holding_bsda.pdf",
                        "content": "Total Holding Valuation: Rs 15,20,000. Account Classification: Regular.",
                    }
                ],
                expected_status_after_turn=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                expected_facts_delta={"portfolio_valuation": Decimal("1520000.00")},
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Depository statement confirms holding exceeded BSDA ceiling, making AMC valid."],
        ),
    ),
]
