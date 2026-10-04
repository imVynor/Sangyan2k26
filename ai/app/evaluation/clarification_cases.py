"""20 Gold Multi-Turn Clarification Benchmark Cases for SANGYAN.

Section 36 Required Scenarios:
1. missing transaction type
2. missing transaction date
3. missing amount
4. missing account type
5. contradictory evidence
6. historical date ambiguity
7. missing organisation
8. document upload resolving uncertainty
9. user declining evidence
10. multiple independent missing fields
11. irrelevant user answer
12. repeated answer
13. changed fact
14. new evidence contradicting old evidence
15. compliance -> violation transition
16. insufficient -> compliance transition
17. insufficient -> violation transition
18. unresolved forever
19. regulatory coverage gap
20. temporal resolution after document upload
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from ai.app.assessment.contracts import AssessmentStatus
from ai.app.extraction.document_extractor import DocumentExtractionPayload, DocumentSpan


@dataclass
class MultiTurnBenchmarkCase:
    case_id: str
    scenario: str
    initial_complaint: str
    reference_date: date | None
    language: str
    initial_expected_status: AssessmentStatus
    expected_first_question_field: str | None
    turn_2_message: str | None
    turn_2_action: str  # ANSWER, DOCUMENT, DECLINE, IRRELEVANT, REPEATED, CONTRADICTION
    turn_2_documents: list[DocumentExtractionPayload] | None = None
    turn_2_decline_field: str | None = None
    expected_final_status: AssessmentStatus = AssessmentStatus.COMPLIANT_WITH_REGULATION
    expected_status_transition: str | None = None
    expected_resolved_uncertainties: list[str] = field(default_factory=list)


GOLD_CLARIFICATION_CASES: list[MultiTurnBenchmarkCase] = [
    # 1. missing transaction type
    MultiTurnBenchmarkCase(
        case_id="CLAR-01",
        scenario="Missing transaction type in initial complaint",
        initial_complaint="Zerodha charged me ₹13.50 on 12 September 2026 for a trade of ABC.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="It was an equity delivery transaction.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> COMPLIANT_WITH_REGULATION",
        expected_resolved_uncertainties=["transaction_type"],
    ),

    # 2. missing transaction date
    MultiTurnBenchmarkCase(
        case_id="CLAR-02",
        scenario="Missing transaction date in fee dispute",
        initial_complaint="I sold delivery shares on Zerodha and was charged ₹13.50. I want to check if this fee was legal.",
        reference_date=None,
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_date",
        turn_2_message="The trade was executed on 2026-08-15.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> COMPLIANT_WITH_REGULATION",
        expected_resolved_uncertainties=["transaction_date"],
    ),

    # 3. missing amount
    MultiTurnBenchmarkCase(
        case_id="CLAR-03",
        scenario="Missing charged amount in grievance",
        initial_complaint="I was charged an unknown fee by Zerodha for an equity delivery trade on 12 September 2026.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="charged_amount",
        turn_2_message="The deduction on my ledger was ₹25.00.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> VIOLATION_CONFIRMED",
        expected_resolved_uncertainties=["charged_amount"],
    ),

    # 4. missing account type (BSDA account)
    MultiTurnBenchmarkCase(
        case_id="CLAR-04",
        scenario="Missing BSDA account qualification for AMC dispute",
        initial_complaint="Zerodha charged me ₹300 for annual maintenance on 2026-02-01. I want to check if this fee was legal.",
        reference_date=date(2026, 2, 1),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="is_bsda",
        turn_2_message="Yes BSDA account is registered with Zerodha.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> VIOLATION_CONFIRMED",
        expected_resolved_uncertainties=["is_bsda"],
    ),

    # 5. contradictory evidence (User ₹50 vs Contract Note ₹15)
    MultiTurnBenchmarkCase(
        case_id="CLAR-05",
        scenario="Contradictory evidence between user assertion and uploaded note",
        initial_complaint="Zerodha charged me ₹50 for a trade on 12 September 2026.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="The trade was delivery. Here is the contract note.",
        turn_2_action="DOCUMENT",
        turn_2_documents=[
            DocumentExtractionPayload(
                document_id="DOC-NOTE-05",
                raw_content="Transaction: Equity Delivery\nDP Charge: ₹13.50",
                content_format="pdf",
                spans=[
                    DocumentSpan(text="Transaction: Equity Delivery", start_char=0, end_char=28),
                    DocumentSpan(text="DP Charge: ₹13.50", start_char=30, end_char=47),
                ],
            )
        ],
        expected_final_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> COMPLIANT_WITH_REGULATION",
        expected_resolved_uncertainties=["transaction_type"],
    ),

    # 6. historical date ambiguity
    MultiTurnBenchmarkCase(
        case_id="CLAR-06",
        scenario="Historical circular transition requiring exact trade date",
        initial_complaint="Angel One charged me ₹20 for equity delivery in 2022. I don't remember the exact day.",
        reference_date=None,
        language="en",
        initial_expected_status=AssessmentStatus.TEMPORALITY_UNRESOLVED,
        expected_first_question_field="transaction_date",
        turn_2_message="The exact date from my email was 2022-05-10.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_status_transition="TEMPORALITY_UNRESOLVED -> COMPLIANT_WITH_REGULATION",
        expected_resolved_uncertainties=["transaction_date"],
    ),

    # 7. missing organisation
    MultiTurnBenchmarkCase(
        case_id="CLAR-07",
        scenario="Missing intermediary organisation identity",
        initial_complaint="My broker charged ₹35 for a delivery trade on 12 September 2026.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="organisation",
        turn_2_message="The broker was Angel One.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> VIOLATION_CONFIRMED",
        expected_resolved_uncertainties=["organisation"],
    ),

    # 8. document upload resolving uncertainty
    MultiTurnBenchmarkCase(
        case_id="CLAR-08",
        scenario="Document upload resolving multiple missing fields at once",
        initial_complaint="I think I was overcharged on my trade with Zerodha.",
        reference_date=None,
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="Uploading my contract note.",
        turn_2_action="DOCUMENT",
        turn_2_documents=[
            DocumentExtractionPayload(
                document_id="DOC-NOTE-08",
                raw_content="Date: 2026-09-12\nType: Equity Delivery\nDP Charges: ₹13.50",
                content_format="pdf",
                spans=[
                    DocumentSpan(text="Date: 2026-09-12", start_char=0, end_char=16),
                    DocumentSpan(text="Type: Equity Delivery", start_char=20, end_char=41),
                    DocumentSpan(text="DP Charges: ₹13.50", start_char=45, end_char=63),
                ],
            )
        ],
        expected_final_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> COMPLIANT_WITH_REGULATION",
        expected_resolved_uncertainties=["charged_amount", "transaction_date", "transaction_type"],
    ),

    # 9. user declining evidence
    MultiTurnBenchmarkCase(
        case_id="CLAR-09",
        scenario="User declines to provide missing transaction type",
        initial_complaint="Zerodha deducted ₹50 on 12 September 2026. I suspect this is illegal.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="I do not have the transaction details or contract note.",
        turn_2_action="DECLINE",
        turn_2_decline_field="transaction_type",
        expected_final_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> EVIDENCE_INSUFFICIENT",
        expected_resolved_uncertainties=[],
    ),

    # 10. multiple independent missing fields
    MultiTurnBenchmarkCase(
        case_id="CLAR-10",
        scenario="Multiple missing fields prioritized sequentially",
        initial_complaint="I noticed a ₹25 fee on Zerodha but have no other info.",
        reference_date=None,
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="It was a delivery trade on 2026-09-12.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> VIOLATION_CONFIRMED",
        expected_resolved_uncertainties=["transaction_type", "transaction_date"],
    ),

    # 11. irrelevant user answer
    MultiTurnBenchmarkCase(
        case_id="CLAR-11",
        scenario="User responds with irrelevant narrative without answering question",
        initial_complaint="Zerodha charged me ₹13.50 on 12 September 2026.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="The stock market is completely rigged and bad.",
        turn_2_action="IRRELEVANT",
        expected_final_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> EVIDENCE_INSUFFICIENT",
        expected_resolved_uncertainties=[],
    ),

    # 12. repeated answer
    MultiTurnBenchmarkCase(
        case_id="CLAR-12",
        scenario="User repeats already known fact instead of answering missing question",
        initial_complaint="Zerodha charged me ₹13.50 on 12 September 2026.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="I already told you they charged ₹13.50.",
        turn_2_action="REPEATED",
        expected_final_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> EVIDENCE_INSUFFICIENT",
        expected_resolved_uncertainties=[],
    ),

    # 13. changed fact (user corrects date)
    MultiTurnBenchmarkCase(
        case_id="CLAR-13",
        scenario="User corrects date from erroneous date to correct operative date",
        initial_complaint="Zerodha charged ₹13.50 for a delivery trade on 2026-01-01.",
        reference_date=date(2026, 1, 1),
        language="en",
        initial_expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_first_question_field=None,
        turn_2_message="Correction: the actual trade date was 2026-09-12.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_status_transition="COMPLIANT_WITH_REGULATION -> COMPLIANT_WITH_REGULATION",
        expected_resolved_uncertainties=[],
    ),

    # 14. new evidence contradicting old evidence
    MultiTurnBenchmarkCase(
        case_id="CLAR-14",
        scenario="Contract note contradicts user assertion of ₹13.50 with ₹25.00",
        initial_complaint="Zerodha charged ₹13.50 on 12 September 2026 for a trade.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="Here is the contract note. It was delivery.",
        turn_2_action="DOCUMENT",
        turn_2_documents=[
            DocumentExtractionPayload(
                document_id="DOC-CN-14",
                raw_content="Type: Equity Delivery\nDP Charge: ₹25.00",
                content_format="pdf",
                spans=[
                    DocumentSpan(text="Type: Equity Delivery", start_char=0, end_char=21),
                    DocumentSpan(text="DP Charge: ₹25.00", start_char=25, end_char=42),
                ],
            )
        ],
        expected_final_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> VIOLATION_CONFIRMED",
        expected_resolved_uncertainties=["transaction_type"],
    ),

    # 15. compliance -> violation transition
    MultiTurnBenchmarkCase(
        case_id="CLAR-15",
        scenario="Case appears compliant until second fee component submitted",
        initial_complaint="Angel One charged me ₹13.50 for delivery trade on 12 September 2026.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_first_question_field=None,
        turn_2_message="Correction: the actual total charge on my contract note was ₹25.00.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_status_transition="COMPLIANT_WITH_REGULATION -> VIOLATION_CONFIRMED",
        expected_resolved_uncertainties=[],
    ),

    # 16. insufficient -> compliance transition
    MultiTurnBenchmarkCase(
        case_id="CLAR-16",
        scenario="Grievance transitions from insufficient to compliant upon answering delivery sale",
        initial_complaint="Zerodha deducted ₹13.50 on 12 September 2026. Is this fee valid?",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="Yes, this was an equity delivery sale of 10 shares.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> COMPLIANT_WITH_REGULATION",
        expected_resolved_uncertainties=["transaction_type"],
    ),

    # 17. insufficient -> violation transition
    MultiTurnBenchmarkCase(
        case_id="CLAR-17",
        scenario="Grievance transitions from insufficient to violation upon establishing delivery",
        initial_complaint="Angel One deducted ₹25.00 on 12 September 2026.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="It was an equity delivery sale.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> VIOLATION_CONFIRMED",
        expected_resolved_uncertainties=["transaction_type"],
    ),

    # 18. unresolved forever (user refuses to provide any documents)
    MultiTurnBenchmarkCase(
        case_id="CLAR-18",
        scenario="Case remains insufficient when essential evidence is permanently unavailable",
        initial_complaint="I lost money on an unknown trade on Zerodha on 12 September 2026.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_first_question_field="transaction_type",
        turn_2_message="I do not have any trade details or statements and decline to provide them.",
        turn_2_action="DECLINE",
        turn_2_decline_field="transaction_type",
        expected_final_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_status_transition="EVIDENCE_INSUFFICIENT -> EVIDENCE_INSUFFICIENT",
        expected_resolved_uncertainties=[],
    ),

    # 19. regulatory coverage gap
    MultiTurnBenchmarkCase(
        case_id="CLAR-19",
        scenario="Unregistered investment advisory entity outside depository coverage",
        initial_complaint="A telegram channel called AlphaTips charged me ₹5000 on 12 September 2026 for stock tips.",
        reference_date=date(2026, 9, 12),
        language="en",
        initial_expected_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
        expected_first_question_field="organisation",
        turn_2_message="They are an unverified group on social media, not a registered broker.",
        turn_2_action="ANSWER",
        expected_final_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
        expected_status_transition="REGULATORY_COVERAGE_UNRESOLVED -> REGULATORY_COVERAGE_UNRESOLVED",
        expected_resolved_uncertainties=[],
    ),

    # 20. temporal resolution after document upload
    MultiTurnBenchmarkCase(
        case_id="CLAR-20",
        scenario="Document upload provides exact historical date resolving circular applicability",
        initial_complaint="Angel One charged me ₹20 for delivery in 2022, but I don't know the date.",
        reference_date=None,
        language="en",
        initial_expected_status=AssessmentStatus.TEMPORALITY_UNRESOLVED,
        expected_first_question_field="transaction_date",
        turn_2_message="Uploading contract note.",
        turn_2_action="DOCUMENT",
        turn_2_documents=[
            DocumentExtractionPayload(
                document_id="DOC-HIST-20",
                raw_content="Execution Date: 2022-05-10\nTransaction Type: Equity Delivery\nDP Fee: ₹20.00",
                content_format="pdf",
                spans=[
                    DocumentSpan(text="Execution Date: 2022-05-10", start_char=0, end_char=26),
                    DocumentSpan(text="Transaction Type: Equity Delivery", start_char=30, end_char=63),
                    DocumentSpan(text="DP Fee: ₹20.00", start_char=65, end_char=79),
                ],
            )
        ],
        expected_final_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_status_transition="TEMPORALITY_UNRESOLVED -> COMPLIANT_WITH_REGULATION",
        expected_resolved_uncertainties=["transaction_date"],
    ),
]
