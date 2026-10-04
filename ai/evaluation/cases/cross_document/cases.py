"""Cross-Document Benchmark Cases (L4) for SANGYAN Evaluation (Phase 7A).

Epistemic foundation:
- 10 cases requiring joint reasoning across multiple independent regulatory and organizational authorities:
  SEBI Statutory Regulations + CDSL/NSDL Depository Bye-laws + Exchange Clearing Rules + Broker Tariffs.
- Tests multi-source retrieval, authority precedence, and compound condition evaluation.
"""

from decimal import Decimal

from ai.app.assessment.contracts import AssessmentStatus
from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedAssessment,
    ExpectedFact,
    ExpectedIssue,
    ExpectedProvision,
    ExpectedSource,
)
from ai.evaluation.corpus.taxonomy import (
    CaseCategory,
    CaseVisibility,
    DifficultyLevel,
    RetrievalRelevance,
)

CASES: list[EvaluationCase] = [
    # 1. Delivery Sell: SEBI + CDSL + Zerodha
    EvaluationCase(
        case_id="CROSS-001",
        title="Delivery share sale debit across SEBI, CDSL, and Zerodha tariff rules",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="Zerodha deducted Rs 15.93 when I sold shares. Is this fee backed by both depository guidelines and SEBI regulations?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("15.93"), data_type="DECIMAL"),
            ExpectedFact(field="transaction_type", expected_value="equity_delivery_sell", required=True),
        ],
        expected_sources=[
            ExpectedSource(source_id="SEBI_MASTER_CIRCULAR_DEMAT", authority="SEBI", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="CDSL_OPERATING_INSTRUCTIONS", authority="CDSL", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="ZERODHA_TARIFF_SCHEDULE", organisation="ORG_ZERODHA", relevance=RetrievalRelevance.REQUIRED),
        ],
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_9_957d01daca9b",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Zerodha tariff establishes the Rs 13.50 + GST contractual rate.",
            ),
            ExpectedProvision(
                provision_id="prov_doc_reg_cdsl_b78236eb9090bedc_sec_3_a65157b112d7",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="CDSL operating instructions govern DP debit authorizations and depository charges.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=[
                "Debit is authorized under CDSL depository operating guidelines.",
                "Charge rate matches published Zerodha tariff schedule.",
            ],
            provenance_notes="Harmonious construction of SEBI demat circular, CDSL bye-laws, and intermediary tariff.",
        ),
    ),

    # 2. Account Freeze for Incomplete KYC: SEBI + CDSL + Angel One
    EvaluationCase(
        case_id="CROSS-002",
        title="Demat account freeze due to PAN-Aadhaar non-linking",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="Angel One froze my demat account on 2026-01-15 citing inoperative PAN. Do depository regulations allow this without a court order?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ANGELONE", required=True),
            ExpectedFact(field="action", expected_value="account_freeze", required=True),
            ExpectedFact(field="reason", expected_value="inoperative_pan", required=True),
        ],
        expected_sources=[
            ExpectedSource(source_id="SEBI_KYC_MASTER_CIRCULAR", authority="SEBI", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="CDSL_KYC_ADVISORY", authority="CDSL", relevance=RetrievalRelevance.REQUIRED),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=[
                "SEBI KYC circular mandates freezing accounts where PAN is inoperative.",
                "CDSL operating instructions require DPs to suspend debit operations for non-compliant accounts.",
            ],
        ),
    ),

    # 3. Margin Pledge/Re-pledge: SEBI + Depository + Broker
    EvaluationCase(
        case_id="CROSS-003",
        title="Margin pledge creation fee and clearing member repledge",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="Broker charged Rs 20 for pledge creation and pledged my shares to Clearing Corporation for margin. Is this dual-action compliant?",
        expected_facts=[
            ExpectedFact(field="action", expected_value="margin_pledge_repledge", required=True),
        ],
        expected_sources=[
            ExpectedSource(source_id="SEBI_MARGIN_PLEDGE_CIRCULAR", authority="SEBI", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="NSDL_PLEDGE_RULES", authority="NSDL", relevance=RetrievalRelevance.SUPPORTING),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=[
                "SEBI margin pledge mechanism requires shares to remain in client demat marked as pledged.",
                "Repledge to Clearing Member / Clearing Corporation is lawful to satisfy margin obligations.",
            ],
        ),
    ),

    # 4. Electronic Contract Note (ECN) Proof: SEBI + IT Act + Broker Logs
    EvaluationCase(
        case_id="CROSS-004",
        title="Electronic Contract Note legal validity and email bounce log",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="Broker claims they emailed the contract note within 24 hours, but my email inbox never received it. Who bears the burden of proof?",
        expected_facts=[
            ExpectedFact(field="document_type", expected_value="electronic_contract_note", required=True),
        ],
        expected_sources=[
            ExpectedSource(source_id="SEBI_ECN_CIRCULAR", authority="SEBI", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="IT_ACT_2000", authority="STATUTORY", relevance=RetrievalRelevance.SUPPORTING),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
            expected_findings=[
                "SEBI regulations place burden on broker to maintain digitally signed log and proof of delivery / non-bounce.",
                "Broker must furnish SMTP server dispatch log to prove compliance.",
            ],
        ),
    ),

    # 5. Unauthorized Trade: Voice Log + Exchange Record + SEBI Circular
    EvaluationCase(
        case_id="CROSS-005",
        title="Unauthorized trade allegation against mandatory voice recording mandate",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="I never authorized the options trade placed by ICICI Direct dealer on 2026-02-12. Broker has not produced any call recording.",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ICICIDIRECT", required=True),
            ExpectedFact(field="disputed_trade", expected_value="dealer_options_trade", required=True),
        ],
        expected_sources=[
            ExpectedSource(source_id="SEBI_PREVENTION_UNAUTHORIZED_TRADES", authority="SEBI", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="EXCHANGE_MANDATORY_RECORDING_CIRCULAR", authority="NSE", relevance=RetrievalRelevance.REQUIRED),
        ],
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_page_18_b378fcf99c73",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI circular mandates telephone recording of instructions; unrecorded orders violate code of conduct.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=[
                "SEBI circular strictly mandates stockbrokers maintain pre-trade voice recording for all phone-placed orders.",
                "Failure to produce telephone recording constitutes regulatory violation in unauthorized trade dispute.",
            ],
            expected_violations=["Violation of SEBI mandate on compulsory recording of order placement instructions."],
        ),
    ),

    # 6. BSDA Valuation & Depository Ledger
    EvaluationCase(
        case_id="CROSS-006",
        title="Joint evaluation of BSDA eligibility across depository holding ledger and broker fee schedule",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="My demat holding value dropped to Rs 3,00,000 before the quarterly billing date, but broker charged regular AMC of Rs 300.",
        expected_facts=[
            ExpectedFact(field="portfolio_value", expected_value=Decimal("300000.00"), data_type="DECIMAL"),
            ExpectedFact(field="charged_amount", expected_value=Decimal("300.00"), data_type="DECIMAL"),
        ],
        expected_sources=[
            ExpectedSource(source_id="SEBI_BSDA_REVISED_CIRCULAR", authority="SEBI", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="CDSL_BSDA_TARIFF", authority="CDSL", relevance=RetrievalRelevance.REQUIRED),
        ],
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_cdsl_b78236eb9090bedc_sec_3_a65157b112d7",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Revised BSDA rules mandate zero AMC on demat holdings <= Rs 4 Lakh on the valuation date.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=[
                "Under SEBI BSDA regulations, holding valuation must be evaluated on date of billing.",
                "Since holding was <= Rs 4,00,000, zero AMC was mandatory under the revised regime.",
            ],
            expected_violations=["Improper AMC levy on eligible BSDA demat account."],
        ),
    ),

    # 7. Clearing Settlement Shortage: Exchange Bye-Laws + Broker Margin
    EvaluationCase(
        case_id="CROSS-007",
        title="Securities payout shortage and auction settlement rules",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="I bought shares on Monday but they were not delivered on Tuesday because the seller defaulted. Broker debited auction valuation amount. Is this legal?",
        expected_facts=[
            ExpectedFact(field="situation", expected_value="settlement_shortage_auction", required=True),
        ],
        expected_sources=[
            ExpectedSource(source_id="NSE_CLEARING_BYELAWS", authority="NSE_CLEARING", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="SEBI_AUCTION_SETTLEMENT_GUIDELINES", authority="SEBI", relevance=RetrievalRelevance.REQUIRED),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=[
                "Clearing corporation auction mechanism governs short deliveries.",
                "Internal shortage or exchange auction closeout prices are debited/credited per clearing bye-laws.",
            ],
        ),
    ),

    # 8. Dividend Distribution & TDS: Companies Act + Income Tax Act + Demat RTA
    EvaluationCase(
        case_id="CROSS-008",
        title="TDS deduction on dividend credited to demat account",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="TCS declared Rs 1,000 dividend on my shares, but only Rs 900 was credited to my bank account. Did the broker or depository steal Rs 100?",
        expected_facts=[
            ExpectedFact(field="gross_dividend", expected_value=Decimal("1000.00"), data_type="DECIMAL"),
            ExpectedFact(field="net_dividend", expected_value=Decimal("900.00"), data_type="DECIMAL"),
        ],
        expected_sources=[
            ExpectedSource(source_id="INCOME_TAX_ACT_SEC_194", authority="INCOME_TAX", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="COMPANIES_ACT_DIVIDEND", authority="MCA", relevance=RetrievalRelevance.SUPPORTING),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=[
                "Under Section 194 of the Income Tax Act, company RTAs deduct 10% TDS on dividends exceeding threshold.",
                "Broker and depository did not deduct the Rs 100; it was deducted by the company at source.",
            ],
        ),
    ),

    # 9. Corporate Action Share Split: Exchange + Depository Credit Timeline
    EvaluationCase(
        case_id="CROSS-009",
        title="Stock split ex-date price adjustment vs delayed demat credit",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="Stock split 1:10 on ex-date 2026-02-10 and price dropped by 90%, but new shares only appeared in my demat account 3 days later. Was I cheated?",
        expected_facts=[
            ExpectedFact(field="corporate_action", expected_value="stock_split", required=True),
        ],
        expected_sources=[
            ExpectedSource(source_id="SEBI_CORPORATE_ACTION_TIMELINE", authority="SEBI", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="CDSL_CORPORATE_ACTION_PROCEDURE", authority="CDSL", relevance=RetrievalRelevance.REQUIRED),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=[
                "Ex-split price adjusts immediately on exchange trading system on ex-date.",
                "Sub-divided shares credit to demat accounts typically occurs within 2-3 working days following record date per depository procedure.",
            ],
        ),
    ),

    # 10. Client Collateral Segregation: SEBI + Clearing Member Report
    EvaluationCase(
        case_id="CROSS-010",
        title="Mandatory client-wise collateral reporting and pledge transparency",
        category=CaseCategory.CROSS_DOCUMENT,
        difficulty=DifficultyLevel.L4,
        visibility=CaseVisibility.PUBLIC,
        user_input="My broker failed to provide the mandatory daily client collateral segregation email showing how my cash margin was deposited with CC.",
        expected_facts=[
            ExpectedFact(field="document_omitted", expected_value="daily_collateral_report", required=True),
        ],
        expected_sources=[
            ExpectedSource(source_id="SEBI_COLLATERAL_SEGREGATION_CIRCULAR", authority="SEBI", relevance=RetrievalRelevance.REQUIRED),
            ExpectedSource(source_id="CLEARING_CORPORATION_COLLATERAL_RULES", authority="NSE_CLEARING", relevance=RetrievalRelevance.REQUIRED),
        ],
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_page_18_8cf99e05aec0",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI collateral segregation framework mandates daily client-wise collateral allocation reporting.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=[
                "SEBI circular mandates stockbrokers send daily collateral reports to clients detailing collateral held at broker, CM, and CC levels.",
            ],
            expected_violations=["Violation of SEBI circular on daily reporting of client collateral segregation."],
        ),
    ),
]
