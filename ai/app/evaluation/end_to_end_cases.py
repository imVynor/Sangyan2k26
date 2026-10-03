"""Ground-truth Gold End-to-End Test Cases for SANGYAN Phase 4 Evaluation.

Epistemic foundation:
- 20 comprehensive end-to-end gold cases connecting:
  Raw User Input / Document -> Fact Extraction -> Case State Integration -> Retrieval -> Assessment -> Generation.
- Evaluates:
  1. Straightforward complaint
  2. Confirmed violation
  3. Confirmed compliance
  4. Policy deviation
  5. Missing evidence
  6. Contradictory evidence
  7. Historical dispute
  8. Temporal ambiguity
  9. Regulatory coverage gap
  10. Fee dispute
  11. GST component (13.50 + 18% = 15.93)
  12. Organisation + regulator interaction
  13. Exact citation request
  14. Multilingual complaint (Hindi)
  15. Multilingual complaint (Hinglish)
  16. Document-derived evidence (contract note snippet)
  17. Ambiguous user statement
  18. Unsupported allegation without facts
  19. Multiple provisions retrieved
  20. Conflicting provisions
"""

from datetime import date
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import AssessmentStatus, EvidenceType


class EndToEndGoldCase(BaseModel):
    """Specification of an end-to-end benchmark test case."""
    case_id: str
    description: str
    raw_input: str
    source_id: str = "user_input"
    source_type: EvidenceType = EvidenceType.USER_STATEMENT
    reference_date: date | None = None
    language: str = "en"
    target_organisation: str | None = None

    # Expected Extraction Outputs
    expected_extracted_fields: dict[str, Any] = Field(default_factory=dict)
    expected_contradictions_count: int = 0

    # Expected Epistemic Assessment & Generation Outputs
    expected_assessment_status: AssessmentStatus
    expected_validation_passed: bool = True
    must_include_citation: bool = True
    expected_disclaimer: bool = True


END_TO_END_GOLD_CASES: list[EndToEndGoldCase] = [
    # 1. Straightforward Complaint
    EndToEndGoldCase(
        case_id="E2E-01",
        description="Investor sold shares on Zerodha and questions DP charges.",
        raw_input="I sold 10 shares of Reliance on 12 September 2026. Zerodha deducted ₹13.50 as DP charges.",
        reference_date=date(2026, 9, 15),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("13.50"),
            "transaction_date": date(2026, 9, 12),
            "transaction_type": "equity_delivery",
            "quantity": 10,
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 2. Confirmed Regulatory Violation
    EndToEndGoldCase(
        case_id="E2E-02",
        description="Broker charged ₹25.00 exceeding statutory ceiling of ₹15.",
        raw_input="On 2026-03-01, Angel One charged me ₹25.00 for a delivery sale of 50 shares of TCS.",
        reference_date=date(2026, 3, 5),
        target_organisation="ORG_ANGELONE",
        expected_extracted_fields={
            "organisation": "ORG_ANGELONE",
            "charged_amount": Decimal("25.00"),
            "transaction_date": date(2026, 3, 1),
            "transaction_type": "equity_delivery",
            "quantity": 50,
        },
        expected_assessment_status=AssessmentStatus.VIOLATION_CONFIRMED,
    ),

    # 3. Confirmed Compliance
    EndToEndGoldCase(
        case_id="E2E-03",
        description="Broker charged ₹13.50 within permitted statutory parameters.",
        raw_input="I sold 5 shares through Zerodha on 15 August 2026 and was charged ₹13.50.",
        reference_date=date(2026, 8, 20),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("13.50"),
            "transaction_date": date(2026, 8, 15),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 4. Organisation Policy Deviation
    EndToEndGoldCase(
        case_id="E2E-04",
        description="Zerodha charged ₹14.00 while its declared tariff schedule specifies ₹13.50.",
        raw_input="Zerodha charged ₹14.00 for my equity delivery sale on 10 January 2026.",
        reference_date=date(2026, 1, 15),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("14.00"),
            "transaction_date": date(2026, 1, 10),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.ORGANISATION_POLICY_DEVIATION,
    ),

    # 5. Missing Evidence (Missing transaction_type)
    EndToEndGoldCase(
        case_id="E2E-05",
        description="Complaint specifies amount and date but transaction_type is unknown.",
        raw_input="On 2026-02-10, Zerodha debited ₹20.00 from my account without any explanation.",
        reference_date=date(2026, 2, 15),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("20.00"),
            "transaction_date": date(2026, 2, 10),
        },
        expected_assessment_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
    ),

    # 6. Contradictory Evidence
    EndToEndGoldCase(
        case_id="E2E-06",
        description="Complaint narrative claims ₹50 was charged but contract note shows ₹15.",
        raw_input="I was charged ₹50.00 for selling shares on 2026-01-10, though the invoice states ₹15.00.",
        reference_date=date(2026, 1, 15),
        expected_extracted_fields={
            "transaction_date": date(2026, 1, 10),
            "transaction_type": "equity_delivery",
        },
        expected_contradictions_count=1,
        expected_assessment_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
    ),

    # 7. Historical Dispute
    EndToEndGoldCase(
        case_id="E2E-07",
        description="2021 incident evaluated against 2026 prospective circular.",
        raw_input="I sold shares on 2021-05-20 and disputed broker awareness notifications from SEBI.",
        reference_date=date(2026, 1, 1),
        expected_extracted_fields={
            "transaction_date": date(2021, 5, 20),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
    ),

    # 8. Temporal Ambiguity
    EndToEndGoldCase(
        case_id="E2E-08",
        description="Complaint where transaction date cannot be resolved because relative date lacks reference_date.",
        raw_input="Yesterday I sold shares through Zerodha and was charged ₹15.00.",
        reference_date=None,  # Intentionally absent reference_date
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("15.00"),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,  # Missing transaction_date
    ),

    # 9. Regulatory Coverage Gap
    EndToEndGoldCase(
        case_id="E2E-09",
        description="Algo trading fee dispute where no statutory SEBI rule exists in corpus.",
        raw_input="On 2026-01-10, Zerodha charged ₹50.00 for algorithmic trading API execution.",
        reference_date=date(2026, 1, 15),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("50.00"),
            "transaction_date": date(2026, 1, 10),
        },
        expected_assessment_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
    ),

    # 10. Fee Dispute (General Delivery)
    EndToEndGoldCase(
        case_id="E2E-10",
        description="Standard delivery fee evaluation with explicit quantities and price.",
        raw_input="Upstox deducted ₹15.00 on 2026-04-12 when I sold 100 shares of INFOSYS.",
        reference_date=date(2026, 4, 15),
        target_organisation="ORG_UPSTOX",
        expected_extracted_fields={
            "organisation": "ORG_UPSTOX",
            "charged_amount": Decimal("15.00"),
            "transaction_date": date(2026, 4, 12),
            "transaction_type": "equity_delivery",
            "quantity": 100,
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 11. GST Component Breakdown
    EndToEndGoldCase(
        case_id="E2E-11",
        description="Dispute of ₹15.93 which represents base tariff ₹13.50 + 18% GST.",
        raw_input="I sold shares on 2026-05-10. Zerodha deducted ₹15.93 as DP charge. I think this is too high.",
        reference_date=date(2026, 5, 15),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("15.93"),
            "transaction_date": date(2026, 5, 10),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 12. Organisation + Regulator Interaction
    EndToEndGoldCase(
        case_id="E2E-12",
        description="Customer queries ICICI Direct debit charges under CDSL regulations.",
        raw_input="ICICI Direct deducted ₹15.00 for equity delivery debit on 2026-02-15 under CDSL depository guidelines.",
        reference_date=date(2026, 2, 20),
        target_organisation="ORG_ICICIDIRECT",
        expected_extracted_fields={
            "organisation": "ORG_ICICIDIRECT",
            "charged_amount": Decimal("15.00"),
            "transaction_date": date(2026, 2, 15),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 13. Exact Citation Request
    EndToEndGoldCase(
        case_id="E2E-13",
        description="Complaint requesting validation under SEBI Master Circular 2024.",
        raw_input="Under SEBI Master Circular 2024, broker debited ₹13.50 on 2026-01-20 for equity delivery.",
        reference_date=date(2026, 1, 25),
        expected_extracted_fields={
            "charged_amount": Decimal("13.50"),
            "transaction_date": date(2026, 1, 20),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 14. Multilingual Complaint (Hindi)
    EndToEndGoldCase(
        case_id="E2E-14",
        description="Hindi complaint: मैंने 12 सितंबर 2026 को शेयर बेचे। ज़ेरोधा ने ₹13.50 काटा।",
        raw_input="मैंने 12 सितंबर 2026 को शेयर बेचे। ज़ेरोधा ने ₹13.50 डीपी शुल्क काटा।",
        reference_date=date(2026, 9, 15),
        language="hi",
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("13.50"),
            "transaction_date": date(2026, 9, 12),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 15. Multilingual Complaint (Hinglish)
    EndToEndGoldCase(
        case_id="E2E-15",
        description="Hinglish complaint: Maine Zerodha me 10 share becha on 15 August 2026 and unhone Rs 13.50 kaata.",
        raw_input="Maine Zerodha me 10 share becha on 15 August 2026 and unhone Rs 13.50 charge kiya.",
        reference_date=date(2026, 8, 20),
        language="hinglish",
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("13.50"),
            "transaction_date": date(2026, 8, 15),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 16. Document-Derived Evidence (Contract Note Snippet)
    EndToEndGoldCase(
        case_id="E2E-16",
        description="Contract note table snippet with formal headers.",
        raw_input="Contract Note Date: 2026-03-15 | Broker: Zerodha Broking Ltd | Settlement: Delivery | DP Charges: ₹13.50",
        source_type=EvidenceType.BROKER_STATEMENT,
        source_id="contract_note_001.txt",
        reference_date=date(2026, 3, 20),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("13.50"),
            "transaction_date": date(2026, 3, 15),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 17. Ambiguous User Statement
    EndToEndGoldCase(
        case_id="E2E-17",
        description="User states: I think Zerodha overcharged me some money last week.",
        raw_input="I think Zerodha overcharged me some money last week.",
        reference_date=date(2026, 5, 1),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
        },
        expected_assessment_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
    ),

    # 18. Unsupported Allegation Without Facts
    EndToEndGoldCase(
        case_id="E2E-18",
        description="Bare allegation: Zerodha is running a scam and stealing funds.",
        raw_input="Zerodha is committing fraud and illegal scams with client funds!",
        reference_date=date(2026, 5, 1),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
        },
        expected_assessment_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
    ),

    # 19. Multiple Provisions Retrieved (Layered Findings)
    EndToEndGoldCase(
        case_id="E2E-19",
        description="Charged ₹14.00 which is within SEBI limit ₹15 but deviates from Zerodha ₹13.50 tariff.",
        raw_input="On 2026-01-20, Zerodha charged ₹14.00 for my delivery sale of shares.",
        reference_date=date(2026, 1, 25),
        target_organisation="ORG_ZERODHA",
        expected_extracted_fields={
            "organisation": "ORG_ZERODHA",
            "charged_amount": Decimal("14.00"),
            "transaction_date": date(2026, 1, 20),
            "transaction_type": "equity_delivery",
        },
        expected_assessment_status=AssessmentStatus.ORGANISATION_POLICY_DEVIATION,
    ),

    # 20. Resolution After Complete Evidence Provided
    EndToEndGoldCase(
        case_id="E2E-20",
        description="Full verified facts with exact dates and amounts allowing definitive compliance.",
        raw_input="On 2026-06-10, ICICI Direct charged ₹15.00 for selling 10 shares of HDFC Bank.",
        reference_date=date(2026, 6, 15),
        target_organisation="ORG_ICICIDIRECT",
        expected_extracted_fields={
            "organisation": "ORG_ICICIDIRECT",
            "charged_amount": Decimal("15.00"),
            "transaction_date": date(2026, 6, 10),
            "transaction_type": "equity_delivery",
            "quantity": 10,
        },
        expected_assessment_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),
]
