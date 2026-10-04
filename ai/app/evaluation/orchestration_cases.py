"""Gold Benchmark Cases for SANGYAN Phase 6A: Case Orchestrator & Epistemic Control Plane.

Covers all 20 required orchestration scenarios:
1. clean first-turn resolution
2. clarification
3. document upload
4. contradiction
5. user correction
6. compliance -> violation
7. violation -> compliance
8. reopening resolved case
9. user decline
10. max clarification termination
11. temporal resolution
12. regulatory coverage gap
13. retrieval failure
14. generation failure
15. duplicate event
16. concurrent updates
17. field-specific evidence precedence
18. multiple claims for one field
19. changed regulatory knowledge snapshot
20. complete audit reconstruction
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from ai.app.assessment.contracts import AssessmentStatus
from ai.app.case.contracts import CaseStatus
from ai.app.extraction.document_extractor import DocumentExtractionPayload, DocumentSpan
from ai.app.orchestration.contracts import OrchestrationInputEvent


@dataclass
class OrchestrationTurnExpectation:
    """Expected outcomes for an individual turn in a benchmark case."""
    turn_index: int
    input_event: OrchestrationInputEvent
    expected_version: int | None = None
    idempotency_key: str | None = None
    expected_status: CaseStatus = CaseStatus.RESOLVED
    expected_assessment_status: AssessmentStatus | None = None
    expected_facts: dict[str, Any] = field(default_factory=dict)
    should_raise_conflict: bool = False
    simulate_generation_failure: bool = False
    simulate_retrieval_failure: bool = False


@dataclass
class OrchestrationGoldCase:
    """Specification of an end-to-end multi-turn orchestration benchmark case."""
    case_id: str
    title: str
    scenario_type: str
    turns: list[OrchestrationTurnExpectation]


def build_orchestration_gold_cases() -> list[OrchestrationGoldCase]:
    """Construct the 20 gold benchmark cases."""
    cases: list[OrchestrationGoldCase] = []

    # -------------------------------------------------------------
    # 1. Clean First-Turn Resolution
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-01",
            title="Clean first-turn resolution",
            scenario_type="first_turn_resolution",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for an equity delivery transaction on 2026-09-12.",
                        reference_date=date(2026, 9, 12),
                    ),
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                    expected_facts={"transaction_type": "equity_delivery", "charged_amount": Decimal("25.00")},
                )
            ],
        )
    )

    # -------------------------------------------------------------
    # 2. Clarification Turn
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-02",
            title="Clarification for missing transaction type",
            scenario_type="clarification_turn",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for a trade on 2026-09-12.",
                        reference_date=date(2026, 9, 12),
                    ),
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                    expected_assessment_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="It was equity delivery.",
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                    expected_facts={"transaction_type": "equity_delivery"},
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 3. Document Upload Turn
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-03",
            title="Document upload resolving uncertainty",
            scenario_type="document_upload",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for a trade.",
                    ),
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                    expected_assessment_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="Here is the contract note.",
                        documents=[
                            DocumentExtractionPayload(
                                document_id="CN-DOC-03",
                                raw_content="Trade Date: 2026-09-12\nType: Equity Delivery\nDP Charge: ₹25.00",
                                content_format="pdf",
                                spans=[DocumentSpan(text="Type: Equity Delivery", start_char=0, end_char=21)],
                            )
                        ],
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                    expected_facts={"transaction_type": "equity_delivery"},
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 4. Contradiction Preservation
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-04",
            title="Contradictory evidence resolved by documentary policy",
            scenario_type="contradiction_preservation",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹50 for selling shares on 2026-09-12.",
                        reference_date=date(2026, 9, 12),
                    ),
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="Wait, here is the contract note.",
                        documents=[
                            DocumentExtractionPayload(
                                document_id="CN-DOC-04",
                                raw_content="Type: Equity Delivery\nDP Charge: ₹13.50",
                                content_format="pdf",
                                spans=[DocumentSpan(text="DP Charge: ₹13.50", start_char=0, end_char=18)],
                            )
                        ],
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                    expected_facts={"charged_amount": Decimal("13.50")},
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 5. User Sequential Correction
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-05",
            title="User sequential correction",
            scenario_type="user_correction",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹13.50 for delivery on 2026-09-12.",
                    ),
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="Correction: it was actually ₹25.00 charged for delivery.",
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                    expected_facts={"charged_amount": Decimal("25.00")},
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 6. Compliance to Violation Transition
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-06",
            title="Compliance to violation transition",
            scenario_type="compliance_to_violation",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹13.50 for delivery on 2026-09-12.",
                    ),
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="Looking closely at the ledger, total DP fee was ₹23.60 with GST.",
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                    expected_facts={"charged_amount": Decimal("23.60")},
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 7. Violation to Compliance Transition
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-07",
            title="Violation to compliance transition",
            scenario_type="violation_to_compliance",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for delivery on 2026-09-12.",
                    ),
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="Actually checking the contract note, the charge was ₹13.50.",
                        documents=[
                            DocumentExtractionPayload(
                                document_id="CN-DOC-07",
                                raw_content="Type: Equity Delivery\nDP Charge: ₹13.50",
                                content_format="pdf",
                                spans=[DocumentSpan(text="DP Charge: ₹13.50", start_char=0, end_char=18)],
                            )
                        ],
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                    expected_facts={"charged_amount": Decimal("13.50")},
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 8. Reopening Resolved Case
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-08",
            title="Reopening a previously resolved case",
            scenario_type="case_reopening",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹15 for delivery on 2026-09-12.",
                    ),
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="Wait, I just saw an additional debit of ₹20 on the monthly ledger.",
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 9. User Decline Handling
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-09",
            title="User declines requested evidence",
            scenario_type="user_decline",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for a trade on 2026-09-12.",
                    ),
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                    expected_assessment_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="I do not have the contract note or statement.",
                        declined_field="transaction_type",
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.CLOSED_INSUFFICIENT,
                    expected_assessment_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 10. Max Clarification Termination
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-10",
            title="Termination after max clarification rounds",
            scenario_type="max_clarifications",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for a trade.",
                    ),
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(user_message="I'm not sure."),
                    expected_version=1,
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                ),
                OrchestrationTurnExpectation(
                    turn_index=3,
                    input_event=OrchestrationInputEvent(user_message="Still looking for it."),
                    expected_version=2,
                    expected_status=CaseStatus.CLOSED_INSUFFICIENT,
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 11. Temporal Resolution
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-11",
            title="Temporal resolution after transaction date supplied",
            scenario_type="temporal_resolution",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹15 for delivery.",
                    ),
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="The trade was on 2026-09-12.",
                        reference_date=date(2026, 9, 12),
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 12. Regulatory Coverage Gap
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-12",
            title="Unregulated entity coverage termination",
            scenario_type="regulatory_coverage_gap",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="CoinDCX charged me 2% crypto trading fees.",
                    ),
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                    expected_assessment_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="CoinDCX is an unregulated cryptocurrency exchange.",
                        declined_field="organisation",
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.CLOSED_INSUFFICIENT,
                    expected_assessment_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 13. Retrieval Failure Handling
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-13",
            title="Retrieval failure handling",
            scenario_type="retrieval_failure",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for delivery.",
                    ),
                    simulate_retrieval_failure=True,
                    expected_status=CaseStatus.RESOLVED,
                )
            ],
        )
    )

    # -------------------------------------------------------------
    # 14. Downstream Generation Failure
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-14",
            title="Generation failure leaves assessment valid",
            scenario_type="generation_failure",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for delivery on 2026-09-12.",
                    ),
                    simulate_generation_failure=True,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                )
            ],
        )
    )

    # -------------------------------------------------------------
    # 15. Idempotent Duplicate Event
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-15",
            title="Duplicate event idempotency check",
            scenario_type="idempotency",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for delivery on 2026-09-12.",
                    ),
                    idempotency_key="IDEMP-ORCH-15",
                    expected_status=CaseStatus.RESOLVED,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for delivery on 2026-09-12.",
                    ),
                    idempotency_key="IDEMP-ORCH-15",
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 16. Optimistic Concurrency Conflict
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-16",
            title="Optimistic concurrency version conflict",
            scenario_type="concurrency_conflict",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(complaint_text="Initial turn."),
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(user_message="Stale update."),
                    expected_version=0,  # Deliberately stale
                    should_raise_conflict=True,
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 17. Field-Specific Evidence Precedence
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-17",
            title="Field-specific evidence precedence check",
            scenario_type="field_specific_precedence",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹50 for selling shares on 2026-09-12.",
                    ),
                    expected_status=CaseStatus.RESOLVED,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="Here is the contract note.",
                        documents=[
                            DocumentExtractionPayload(
                                document_id="CN-17",
                                raw_content="Type: Equity Delivery\nDP Charge: ₹13.50",
                                content_format="pdf",
                                spans=[DocumentSpan(text="DP Charge: ₹13.50", start_char=0, end_char=18)],
                            )
                        ],
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_facts={"charged_amount": Decimal("13.50")},
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 18. Multiple Claims for One Field
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-18",
            title="Multiple claims tracked for one field",
            scenario_type="multiple_claims",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹50 for delivery on 2026-09-12.",
                    ),
                    expected_status=CaseStatus.RESOLVED,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="Support chat stated the charge was ₹20.",
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                ),
                OrchestrationTurnExpectation(
                    turn_index=3,
                    input_event=OrchestrationInputEvent(
                        user_message="Contract note shows ₹13.50.",
                        documents=[
                            DocumentExtractionPayload(
                                document_id="CN-18",
                                raw_content="DP Charge: ₹13.50",
                                content_format="pdf",
                                spans=[DocumentSpan(text="DP Charge: ₹13.50", start_char=0, end_char=16)],
                            )
                        ],
                    ),
                    expected_version=2,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                    expected_facts={"charged_amount": Decimal("13.50")},
                ),
            ],
        )
    )

    # -------------------------------------------------------------
    # 19. Regulatory Knowledge Snapshot Tracking
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-19",
            title="Regulatory knowledge snapshot tracking",
            scenario_type="knowledge_snapshot",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for delivery on 2026-09-12.",
                    ),
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                )
            ],
        )
    )

    # -------------------------------------------------------------
    # 20. Complete Audit Reconstruction
    # -------------------------------------------------------------
    cases.append(
        OrchestrationGoldCase(
            case_id="ORCH-20",
            title="Complete audit reconstruction across turns",
            scenario_type="audit_reconstruction",
            turns=[
                OrchestrationTurnExpectation(
                    turn_index=1,
                    input_event=OrchestrationInputEvent(
                        complaint_text="Zerodha charged me ₹25 for a trade on 2026-09-12.",
                    ),
                    expected_status=CaseStatus.REQUIRES_CLARIFICATION,
                ),
                OrchestrationTurnExpectation(
                    turn_index=2,
                    input_event=OrchestrationInputEvent(
                        user_message="It was equity delivery.",
                    ),
                    expected_version=1,
                    expected_status=CaseStatus.RESOLVED,
                    expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
                ),
            ],
        )
    )

    return cases
