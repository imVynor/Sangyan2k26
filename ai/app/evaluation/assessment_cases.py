"""Gold Assessment Benchmark Cases for SANGYAN Epistemic Evaluation.

Epistemic foundation:
- 16 manually verified gold benchmark cases grounded in actual regulatory & organisation provisions.
- Covers:
  1. Confirmed regulatory violation (charged ₹25 against CDSL/SEBI maximum ceiling of ₹15)
  2. Confirmed compliance (charged ₹13.50 within permitted tariff)
  3. Organisation policy deviation (broker charged ₹20 while its own tariff schedule states ₹13.50)
  4. Insufficient evidence: missing transaction_type
  5. Insufficient evidence: missing charged_amount
  6. Historical case: 2021 incident evaluated against 2026 rule (NOT_APPLICABLE)
  7. Temporal ambiguity: historical incident with no operative historical circular (TEMPORALITY_UNRESOLVED)
  8. Unresolved conflicting provisions: contradictory tariff limits with no resolution basis
  9. Resolved conflicting provisions: regulatory ceiling overrides intermediary tariff
  10. Exception case: BSDA account qualifying for nil AMC exemption
  11. Cross-organisation case: ICICI Direct customer with CDSL depository rule
  12. Tiered fee calculation: turnover-based brokerage within permissible slab
  13. Percentage brokerage with cap calculation
  14. Regulatory coverage unresolved: only organisation FAQ retrieved
  15. Contradicted evidence: conflicting statements on charged amount
  16. Multi-layered assessment: regulatory compliant but organisation policy deviation
"""

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import (
    AssessmentRequest,
    AssessmentStatus,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceType,
    RuleOutcome,
)
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult


class GoldAssessmentCase(BaseModel):
    """Specification of a ground-truth gold assessment test case."""
    case_id: str
    description: str
    request: AssessmentRequest
    expected_status: AssessmentStatus
    expected_unresolved_conflicts: int = 0
    expected_missing_fields: list[str] = Field(default_factory=list)
    expected_rule_outcome: RuleOutcome | None = None
    expected_safety_invariant: str = "PASS"


def make_retrieval_result(
    provision_id: str,
    rank: int = 1,
    relevance_score: float = 0.9,
    temporal_status: str = "CURRENT",
    applicability_status: str = "APPLICABLE",
    retrieval_methods: list[str] | None = None,
    provision_text: str = "",
    authority: str | None = None,
    organisation_id: str | None = None,
    source_class: str = "REGULATORY",
    document_id: str = "doc_test",
    section_id: str = "sec_1",
    effective_from: date | None = None,
    effective_to: date | None = None,
    citation: str = "Official Circular",
    source_url: str = "https://www.sebi.gov.in/test.pdf",
    provision_type: str = "FEE_OR_CHARGE",
) -> RetrievalResult:
    """Helper to construct strictly valid RetrievalResults for assessment benchmark."""
    return RetrievalResult(
        provision_id=provision_id,
        rank=rank,
        relevance_score=relevance_score,
        temporal_status=temporal_status,
        applicability_status=applicability_status,
        retrieval_methods=retrieval_methods or ["lexical", "vector"],
        provision_type=provision_type,
        provision_text=provision_text,
        authority=authority,
        organisation_id=organisation_id,
        source_class=source_class,
        document_id=document_id,
        section_id=section_id,
        citation=citation,
        source_url=source_url,
        effective_from=effective_from,
        effective_to=effective_to,
        provenance=None,
    )


# Canonical mock provisions representing real corpus instruments
RES_SEBI_MAX_FEE = make_retrieval_result(
    provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_sec_2_c1",
    provision_text="Depository participants shall not charge more than ₹15 per debit transaction.",
    authority="SEBI",
    source_class="REGULATORY",
    document_id="doc_reg_sebi_1fa7fdbd6f70d052",
    section_id="sec_2",
    effective_from=date(2024, 1, 1),
    citation="SEBI Master Circular 2024",
)

RES_CDSL_TARIFF = make_retrieval_result(
    provision_id="prov_doc_reg_cdsl_5d21271c12f3a487_sec_5_p1",
    provision_text="CDSL depository debit fee ceiling is fixed at ₹15 per delivery instruction.",
    authority="CDSL",
    source_class="REGULATORY",
    document_id="doc_reg_cdsl_5d21271c12f3a487",
    section_id="sec_5",
    effective_from=date(2023, 6, 1),
    citation="CDSL Tariff Schedule",
)

RES_ZERODHA_TARIFF = make_retrieval_result(
    provision_id="prov_doc_org_org_zerodha_591f5ecebb5b3fc3_sec_3_p1",
    provision_text="Zerodha DP charge is ₹13.50 per scrip per day upon sale of securities.",
    authority=None,
    organisation_id="ORG_ZERODHA",
    source_class="ORGANISATION_POLICY",
    document_id="doc_org_org_zerodha_591f5ecebb5b3fc3",
    section_id="sec_3",
    effective_from=date(2023, 1, 1),
    citation="Zerodha Tariff Policy",
    source_url="https://zerodha.com/charges",
)

RES_HISTORICAL_2026_RULE = make_retrieval_result(
    provision_id="prov_doc_reg_sebi_0822d6895e61d08d_sec_1_p1",
    provision_text="Project Jagrook investor awareness mandates applicable from 1 October 2026.",
    authority="SEBI",
    source_class="REGULATORY",
    document_id="doc_reg_sebi_0822d6895e61d08d",
    section_id="sec_1",
    effective_from=date(2026, 10, 1),
    citation="SEBI Jagrook Circular",
)

RES_ANGELONE_TARIFF = make_retrieval_result(
    provision_id="prov_doc_org_org_angelone_15f2261ebececfc3_sec_4_p1",
    provision_text="Angel One levies ₹20 per debit transaction.",
    authority=None,
    organisation_id="ORG_ANGELONE",
    source_class="ORGANISATION_POLICY",
    document_id="doc_org_org_angelone_15f2261ebececfc3",
    section_id="sec_4",
    effective_from=date(2024, 2, 1),
    citation="Angel One Tariff Schedule",
    source_url="https://www.angelone.in/charges",
)


GOLD_ASSESSMENT_CASES: list[GoldAssessmentCase] = [
    # 1. Confirmed Regulatory Violation (Charged ₹25 > SEBI/CDSL limit ₹15)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-01",
        description="Broker charged ₹25 DP fee exceeding statutory ceiling of ₹15.",
        request=AssessmentRequest(
            case_id="CASE-VIO-01",
            case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("15.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-01A",
                    case_id="CASE-VIO-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("25.00"),
                    source="contract_note.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-01B",
                    case_id="CASE-VIO-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 2, 10),
                    source="contract_note.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 2, 10),
        ),
        expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_rule_outcome=RuleOutcome.VIOLATED,
    ),

    # 2. Confirmed Compliance (Charged ₹13.50 <= ₹15)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-02",
        description="Zerodha charged ₹13.50 which is within the ₹15 statutory ceiling.",
        request=AssessmentRequest(
            case_id="CASE-CMP-01",
            case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("15.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-02A",
                    case_id="CASE-CMP-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("13.50"),
                    source="contract_note.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-02B",
                    case_id="CASE-CMP-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 3, 1),
                    source="contract_note.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 3, 1),
        ),
        expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_rule_outcome=RuleOutcome.SATISFIED,
    ),

    # 3. Organisation Policy Deviation (Charged ₹20 while Zerodha's own schedule says ₹13.50)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-03",
        description="Zerodha charged ₹20 in violation of its declared tariff schedule of ₹13.50.",
        request=AssessmentRequest(
            case_id="CASE-DEV-01",
            case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("13.50")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-03A",
                    case_id="CASE-DEV-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("20.00"),
                    source="ledger_statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-03B",
                    case_id="CASE-DEV-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 1, 15),
                    source="ledger_statement.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_ZERODHA_TARIFF],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 1, 15),
            target_organisation="ORG_ZERODHA",
            require_regulatory_coverage=False,
        ),
        expected_status=AssessmentStatus.ORGANISATION_POLICY_DEVIATION,
        expected_rule_outcome=RuleOutcome.VIOLATED,
    ),

    # 4. Insufficient Evidence (Missing transaction_type)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-04",
        description="Charged amount is known but transaction_type is unknown.",
        request=AssessmentRequest(
            case_id="CASE-INSUFF-01",
            case_facts={"issue_category": "dp_charges"},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-04A",
                    case_id="CASE-INSUFF-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("20.00"),
                    source="statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-04B",
                    case_id="CASE-INSUFF-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 1, 15),
                    source="statement.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 1, 15),
        ),
        expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_missing_fields=["transaction_type"],
    ),

    # 5. Insufficient Evidence (Missing charged_amount)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-05",
        description="User claims illegal charge but provides no charged_amount.",
        request=AssessmentRequest(
            case_id="CASE-INSUFF-02",
            case_facts={"transaction_type": "equity_delivery"},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-05B",
                    case_id="CASE-INSUFF-02",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 1, 15),
                    source="statement.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 1, 15),
        ),
        expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_missing_fields=["charged_amount"],
    ),

    # 6. Historical Case Temporal Mismatch (2021 incident applied to 2026 rule)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-06",
        description="2021 incident evaluated against circular effective from October 2026.",
        request=AssessmentRequest(
            case_id="CASE-TEMP-01",
            case_facts={"transaction_type": "equity_delivery", "charged_amount": Decimal("10.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-06A",
                    case_id="CASE-TEMP-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("10.00"),
                    source="statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-06B",
                    case_id="CASE-TEMP-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2021, 5, 20),
                    source="statement.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_HISTORICAL_2026_RULE],
                total_candidates_found=1,
            ),
            incident_date=date(2021, 5, 20),
        ),
        expected_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
    ),

    # 7. Temporal Ambiguity (Incident date missing and rule not current)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-07",
        description="Incident date is unresolved and retrieved provision is historical.",
        request=AssessmentRequest(
            case_id="CASE-TEMP-02",
            case_facts={"transaction_type": "equity_delivery", "charged_amount": Decimal("15.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-07A",
                    case_id="CASE-TEMP-02",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("15.00"),
                    source="statement.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[
                    make_retrieval_result(
                        provision_id="prov_doc_historical_unknown",
                        temporal_status="UNKNOWN",
                        applicability_status="TEMPORALITY_UNRESOLVED",
                        provision_text="Historical procedural guideline with undefined enforcement date.",
                        authority="SEBI",
                        source_class="REGULATORY",
                        document_id="doc_historical_unknown",
                    )
                ],
                total_candidates_found=1,
            ),
            incident_date=None,
        ),
        expected_status=AssessmentStatus.TEMPORALITY_UNRESOLVED,
    ),

    # 8. Unresolved Conflicting Provisions (Two same-level provisions contradict without precedence)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-08",
        description="Two broker policies state contradictory DP tariffs (₹15 vs ₹20) with no precedence.",
        request=AssessmentRequest(
            case_id="CASE-CONF-01",
            case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("15.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-08A",
                    case_id="CASE-CONF-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("18.00"),
                    source="statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-08B",
                    case_id="CASE-CONF-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 1, 15),
                    source="statement.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[
                    make_retrieval_result(
                        provision_id="prov_doc_policy_A",
                        provision_text="Policy A states fee limit ₹15.",
                        organisation_id="ORG_TEST",
                        source_class="ORGANISATION_POLICY",
                        document_id="doc_policy_A",
                        effective_from=date(2024, 1, 1),
                    ),
                    make_retrieval_result(
                        provision_id="prov_doc_policy_B",
                        provision_text="Policy B states fee limit ₹20.",
                        organisation_id="ORG_TEST",
                        source_class="ORGANISATION_POLICY",
                        document_id="doc_policy_B",
                        effective_from=date(2024, 1, 1),
                    ),
                ],
                total_candidates_found=2,
            ),
            incident_date=date(2026, 1, 15),
            require_regulatory_coverage=False,
        ),
        expected_status=AssessmentStatus.CONFLICTING_PROVISIONS,
        expected_unresolved_conflicts=1,
    ),

    # 9. Resolved Conflicting Provisions (Regulatory ceiling ₹15 overrides Broker tariff ₹20)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-09",
        description="Regulatory ceiling of ₹15 overrides broker's published ₹20 tariff via authority hierarchy.",
        request=AssessmentRequest(
            case_id="CASE-CONF-02",
            case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("15.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-09A",
                    case_id="CASE-CONF-02",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("20.00"),
                    source="statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-09B",
                    case_id="CASE-CONF-02",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 1, 15),
                    source="statement.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE, RES_ANGELONE_TARIFF],
                total_candidates_found=2,
            ),
            incident_date=date(2026, 1, 15),
            target_organisation="ORG_ANGELONE",
        ),
        expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_unresolved_conflicts=0,
    ),

    # 10. Exception Case (BSDA Account qualifying for nil AMC)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-10",
        description="Customer account is verified as BSDA, triggering nil maintenance fee exception.",
        request=AssessmentRequest(
            case_id="CASE-EX-01",
            case_facts={"transaction_type": "amc", "is_bsda": True, "account_type": "BSDA", "permitted_amount": Decimal("0.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-10A",
                    case_id="CASE-EX-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("0.00"),
                    source="account_statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-10B",
                    case_id="CASE-EX-01",
                    evidence_type=EvidenceType.DOCUMENT,
                    field_name="is_bsda",
                    value=True,
                    source="holding_statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-10C",
                    case_id="CASE-EX-01",
                    evidence_type=EvidenceType.DOCUMENT,
                    field_name="account_type",
                    value="BSDA",
                    source="holding_statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-10D",
                    case_id="CASE-EX-01",
                    evidence_type=EvidenceType.SYSTEM_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 2, 1),
                    source="system",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 2, 1),
        ),
        expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    ),

    # 11. Cross-Organisation Case (ICICI Direct investor checking CDSL depository rule)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-11",
        description="ICICI Direct client confirms debit fee against CDSL regulatory provision.",
        request=AssessmentRequest(
            case_id="CASE-CROSS-01",
            case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("15.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-11A",
                    case_id="CASE-CROSS-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("15.00"),
                    source="icici_contract.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-11B",
                    case_id="CASE-CROSS-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 2, 15),
                    source="icici_contract.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_CDSL_TARIFF],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 2, 15),
            target_organisation="ORG_ICICIDIRECT",
        ),
        expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_rule_outcome=RuleOutcome.SATISFIED,
    ),

    # 12. Tiered Brokerage Calculation
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-12",
        description="Brokerage calculated on delivery trade conforms to regulatory ceiling.",
        request=AssessmentRequest(
            case_id="CASE-FEE-01",
            case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("15.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-12A",
                    case_id="CASE-FEE-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("20.00"),
                    source="contract_note.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-12B",
                    case_id="CASE-FEE-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 1, 10),
                    source="contract_note.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 1, 10),
        ),
        expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
        expected_rule_outcome=RuleOutcome.VIOLATED,
    ),

    # 13. Percentage Brokerage within Cap
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-13",
        description="Broker charged ₹12 on ₹10,000 turnover which conforms to ₹15 statutory ceiling.",
        request=AssessmentRequest(
            case_id="CASE-PCT-01",
            case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("15.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-13A",
                    case_id="CASE-PCT-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("12.00"),
                    source="trade_report.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-13B",
                    case_id="CASE-PCT-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 2, 5),
                    source="trade_report.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 2, 5),
        ),
        expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        expected_rule_outcome=RuleOutcome.SATISFIED,
    ),

    # 14. Regulatory Coverage Unresolved (Only organisation FAQ retrieved)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-14",
        description="Only intermediary FAQ retrieved when regulatory coverage is required.",
        request=AssessmentRequest(
            case_id="CASE-REG-UNRES-01",
            case_facts={"transaction_type": "algo_trading", "charged_amount": Decimal("50.00")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-14A",
                    case_id="CASE-REG-UNRES-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("50.00"),
                    source="statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-14B",
                    case_id="CASE-REG-UNRES-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 1, 10),
                    source="statement.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_ZERODHA_TARIFF],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 1, 10),
            require_regulatory_coverage=True,
        ),
        expected_status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
    ),

    # 15. Contradicted Evidence (Customer claims ₹50 but broker contract note shows ₹15)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-15",
        description="Contradictory evidence on charged amount without independent corroboration.",
        request=AssessmentRequest(
            case_id="CASE-CONTRA-01",
            case_facts={"transaction_type": "equity_delivery"},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-15A",
                    case_id="CASE-CONTRA-01",
                    evidence_type=EvidenceType.USER_STATEMENT,
                    field_name="charged_amount",
                    value=Decimal("50.00"),
                    source="user_narrative",
                ),
                EvidenceItem(
                    evidence_id="EVID-15B",
                    case_id="CASE-CONTRA-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("15.00"),
                    source="broker_contract_note.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-15C",
                    case_id="CASE-CONTRA-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 1, 10),
                    source="broker_contract_note.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE],
                total_candidates_found=1,
            ),
            incident_date=date(2026, 1, 10),
        ),
        expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        expected_missing_fields=["charged_amount"],
    ),

    # 16. Multi-Layered Assessment (Regulatory Compliant ₹14 <= ₹15, but Zerodha Policy Deviation ₹14 > ₹13.50)
    GoldAssessmentCase(
        case_id="GOLD-ASSESS-16",
        description="Charged ₹14 is compliant with SEBI ceiling (₹15) but deviates from Zerodha declared tariff (₹13.50).",
        request=AssessmentRequest(
            case_id="CASE-LAYERED-01",
            case_facts={"transaction_type": "equity_delivery", "permitted_amount": Decimal("13.50")},
            evidence_items=[
                EvidenceItem(
                    evidence_id="EVID-16A",
                    case_id="CASE-LAYERED-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="charged_amount",
                    value=Decimal("14.00"),
                    source="statement.pdf",
                ),
                EvidenceItem(
                    evidence_id="EVID-16B",
                    case_id="CASE-LAYERED-01",
                    evidence_type=EvidenceType.TRANSACTION_RECORD,
                    field_name="transaction_date",
                    value=date(2026, 1, 20),
                    source="statement.pdf",
                ),
            ],
            retrieval_response=RetrievalResponse(
                results=[RES_SEBI_MAX_FEE, RES_ZERODHA_TARIFF],
                total_candidates_found=2,
            ),
            incident_date=date(2026, 1, 20),
            target_organisation="ORG_ZERODHA",
            require_regulatory_coverage=True,
        ),
        expected_status=AssessmentStatus.ORGANISATION_POLICY_DEVIATION,
        expected_rule_outcome=RuleOutcome.VIOLATED,
    ),
]
