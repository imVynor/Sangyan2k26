"""Contradictory Evidence Benchmark Cases (L3) for SANGYAN Evaluation (Phase 7A).

Epistemic foundation:
- 10 cases with explicit, competing claims (User Statement vs Contract Note / Broker Ledger / Bank Mandate).
- Tests contradiction detection, preservation of competing claims, and evidence policy resolution.
- Enforces precedence: verified document evidence overrides subjective user assertion on empirical facts.
"""

from datetime import date
from decimal import Decimal

from ai.app.assessment.contracts import AssessmentStatus
from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedAssessment,
    ExpectedClaim,
    ExpectedFact,
    ExpectedIssue,
    ExpectedProvision,
)
from ai.evaluation.corpus.taxonomy import (
    AdversarialSubtype,
    CaseCategory,
    CaseVisibility,
    ClaimRelationshipType,
    DifficultyLevel,
    RetrievalRelevance,
)

CASES: list[EvaluationCase] = [
    # 1. User says ₹50 vs Contract Note ₹15.93
    EvaluationCase(
        case_id="CONTRA-001",
        title="User assertion of ₹50 charge contradicted by contract note ₹15.93",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="Zerodha took Rs 50 from my account for a single delivery trade. Here is my contract note showing the transaction.",
        context={
            "attached_document": "contract_note_001.pdf",
            "document_content": "Zerodha Broking Limited. Contract Note Ref: CN-2026-9912. Total Brokerage: Rs 0.00. Exchange Txn Charge: Rs 0.15. GST: Rs 2.28. DP Charges: Rs 13.50. Total Statutory/DP Deductions: Rs 15.93.",
        },
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="charged_amount", expected_value=Decimal("15.93"), data_type="DECIMAL"),
        ],
        expected_claims=[
            ExpectedClaim(
                claim_id="CLM-01",
                field_name="charged_amount",
                claimed_value=Decimal("50.00"),
                source_type="USER_STATEMENT",
                relationship_to="CLM-02",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
                expected_resolution=str(Decimal("15.93")),
            ),
            ExpectedClaim(
                claim_id="CLM-02",
                field_name="charged_amount",
                claimed_value=Decimal("15.93"),
                source_type="DOCUMENT",
                relationship_to="CLM-01",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
                expected_resolution=str(Decimal("15.93")),
            ),
        ],
        expected_issues=ExpectedIssue(
            primary_issue="Discrepancy between alleged fee and verified contract note charges",
            secondary_issues=["DP charge verification"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_9_957d01daca9b",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Zerodha tariff authorizes Rs 13.50 + 18% GST (Rs 15.93) on delivery debit.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Contract note proves actual deduction was Rs 15.93, which matches authorized tariff."],
            provenance_notes="Contract note conclusively refutes user's subjective assertion of Rs 50.",
        ),
    ),

    # 2. User claims delivery vs Ledger shows intraday square-off
    EvaluationCase(
        case_id="CONTRA-002",
        title="User claims equity delivery but trade log proves intraday square-off",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="I bought shares for long term delivery in Angel One, but they charged me Rs 20 brokerage and squared off my position at 3:15 PM.",
        context={
            "attached_document": "order_log_002.pdf",
            "document_content": "Order Type: MIS (Margin Intraday Square-off). Executed at: 09:30. Auto Square-off Executed by RMS at 15:15 PM.",
        },
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ANGELONE", required=True),
            ExpectedFact(field="product_code", expected_value="MIS", required=True),
        ],
        expected_claims=[
            ExpectedClaim(
                claim_id="CLM-03",
                field_name="transaction_type",
                claimed_value="equity_delivery",
                source_type="USER_STATEMENT",
                relationship_to="CLM-04",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
                expected_resolution="intraday_mis",
            ),
            ExpectedClaim(
                claim_id="CLM-04",
                field_name="transaction_type",
                claimed_value="intraday_mis",
                source_type="DOCUMENT",
                relationship_to="CLM-03",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
                expected_resolution="intraday_mis",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["System logs prove trade was placed under intraday MIS product code, subject to mandatory auto square-off."],
        ),
    ),

    # 3. Marketing oral claim vs Signed tariff agreement
    EvaluationCase(
        case_id="CONTRA-003",
        title="Oral marketing assertion contradicted by signed tariff sheet",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="An Angel One sales executive told me on the phone that F&O brokerage would be completely free forever, but I was charged Rs 20 per order.",
        context={
            "attached_document": "signed_client_agreement.pdf",
            "document_content": "Client Registration Kit. Schedule of Brokerage: Equity Futures and Options: Rs 20 per executed order or 0.25% whichever is lower. Signed by Client on 2025-08-10.",
        },
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ANGELONE", required=True),
            ExpectedFact(field="agreed_rate", expected_value=Decimal("20.00"), data_type="DECIMAL"),
        ],
        expected_claims=[
            ExpectedClaim(
                claim_id="CLM-05",
                field_name="fno_brokerage",
                claimed_value=Decimal("0.00"),
                source_type="USER_STATEMENT",
                relationship_to="CLM-06",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
                expected_resolution=str(Decimal("20.00")),
            ),
            ExpectedClaim(
                claim_id="CLM-06",
                field_name="fno_brokerage",
                claimed_value=Decimal("20.00"),
                source_type="DOCUMENT",
                relationship_to="CLM-05",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
                expected_resolution=str(Decimal("20.00")),
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Written client registration agreement and tariff schedule prevail over informal oral assertions."],
        ),
    ),

    # 4. Exchange execution discrepancy (NSE vs BSE)
    EvaluationCase(
        case_id="CONTRA-004",
        title="Exchange venue contradiction between ledger and confirmation",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="I instructed my broker to buy shares on NSE, but they traded on BSE where transaction charges differ.",
        context={
            "attached_document": "exchange_trade_confirmation.pdf",
            "document_content": "Exchange: BSE. Order No: 99482. Trade Time: 10:14:22. Scrip: RELIANCE.",
        },
        expected_facts=[
            ExpectedFact(field="executed_exchange", expected_value="BSE", required=True),
        ],
        expected_claims=[
            ExpectedClaim(
                claim_id="CLM-07",
                field_name="exchange",
                claimed_value="NSE",
                source_type="USER_STATEMENT",
                relationship_to="CLM-08",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
            ),
            ExpectedClaim(
                claim_id="CLM-08",
                field_name="exchange",
                claimed_value="BSE",
                source_type="DOCUMENT",
                relationship_to="CLM-07",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Unless smart order routing agreement was breached, broker execution on designated registered exchange is valid."],
        ),
    ),

    # 5. User alleges unauthorized debit vs Bank auto-mandate
    EvaluationCase(
        case_id="CONTRA-005",
        title="Allegation of unauthorized bank debit refuted by e-mandate",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="Groww stole Rs 5,000 from my bank account without my permission on 2026-02-01.",
        context={
            "attached_document": "nach_mandate_record.pdf",
            "document_content": "NPCI E-Mandate UMRN: NACH00000000049281. User Name: Verified. Purpose: Monthly Mutual Fund SIP. Authenticated via NetBanking on 2025-05-15.",
        },
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_GROWW", required=True),
            ExpectedFact(field="mandate_verified", expected_value=True, data_type="BOOLEAN"),
        ],
        expected_claims=[
            ExpectedClaim(
                claim_id="CLM-09",
                field_name="authorization_status",
                claimed_value="UNAUTHORIZED",
                source_type="USER_STATEMENT",
                relationship_to="CLM-10",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
                expected_resolution="AUTHORIZED",
            ),
            ExpectedClaim(
                claim_id="CLM-10",
                field_name="authorization_status",
                claimed_value="AUTHORIZED",
                source_type="DOCUMENT",
                relationship_to="CLM-09",
                relationship_type=ClaimRelationshipType.CONTRADICTORY,
                expected_resolution="AUTHORIZED",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Debit executed pursuant to authenticated NPCI auto-mandate registered by user."],
        ),
    ),

    # 6. Trade timing conflict
    EvaluationCase(
        case_id="CONTRA-006",
        title="Trade execution timestamp contradiction",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="I placed the buy order at 11:00 AM after seeing market news, but broker filled it at high price at 9:16 AM.",
        context={
            "attached_document": "exchange_order_audit_trail.pdf",
            "document_content": "Exchange Audit Trail. Order Ingestion: 09:15:45 AM. Execution: 09:16:02 AM. IP: 103.21.44.12.",
        },
        expected_facts=[
            ExpectedFact(field="execution_time", expected_value="09:16:02", required=True),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Exchange audit trail confirms order was entered and matched at 09:16 AM, contradicting user recollection."],
        ),
    ),

    # 7. DP charge amount conflict
    EvaluationCase(
        case_id="CONTRA-007",
        title="DP charge rate dispute (User claims ₹35 vs Contract Note ₹13.50)",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="Zerodha billed me Rs 35 DP charge on selling shares. That exceeds the standard limit.",
        context={
            "attached_document": "contract_note_007.pdf",
            "document_content": "Depository Participant Charges: Rs 13.50. Integrated GST (18%): Rs 2.43. Total: Rs 15.93.",
        },
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="base_dp_charge", expected_value=Decimal("13.50"), data_type="DECIMAL"),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Document establishes DP charge was Rs 13.50 + GST, not Rs 35 as alleged."],
        ),
    ),

    # 8. BSDA status conflict
    EvaluationCase(
        case_id="CONTRA-008",
        title="BSDA zero AMC claim contradicted by depository valuation record",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="I am a BSDA account holder so ICICI Direct cannot charge me any AMC. Why was Rs 300 deducted?",
        context={
            "attached_document": "demat_holding_statement.pdf",
            "document_content": "ICICI Securities. Demat Account Status: Regular Non-BSDA. Total Portfolio Holding Valuation as of date: Rs 14,50,000.",
        },
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ICICIDIRECT", required=True),
            ExpectedFact(field="portfolio_valuation", expected_value=Decimal("1450000.00"), data_type="DECIMAL"),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Portfolio valuation of Rs 14.5 lakh exceeds BSDA threshold, disqualifying account from zero AMC."],
        ),
    ),

    # 9. Stop-loss execution claim
    EvaluationCase(
        case_id="CONTRA-009",
        title="User claims stop-loss was ignored but exchange log shows limit gap",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="Upstox failed to trigger my stop-loss order at Rs 100 and let my losses run.",
        context={
            "attached_document": "order_book_sl.pdf",
            "document_content": "Order Type: SL-Limit. Trigger Price: Rs 100. Limit Price: Rs 99.80. Market open gap down at Rs 98.00. Trigger reached but limit price not traded.",
        },
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_UPSTOX", required=True),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["SL-Limit order was triggered correctly but market price gapped below limit price, preventing fill."],
        ),
    ),

    # 10. Deposit settlement date conflict
    EvaluationCase(
        case_id="CONTRA-010",
        title="Fund deposit receipt date contradiction",
        category=CaseCategory.CONTRADICTORY,
        difficulty=DifficultyLevel.L3,
        adversarial_subtype=AdversarialSubtype.CONTRADICTORY_EVIDENCE,
        visibility=CaseVisibility.PUBLIC,
        user_input="I deposited funds via bank on Monday morning 2026-01-12, but Zerodha only credited it on Wednesday.",
        context={
            "attached_document": "bank_statement_deposit.pdf",
            "document_content": "Bank of Baroda. Transaction: NEFT to Zerodha Broking. Value Date: 2026-01-14 (Wednesday). Remarks: Delayed clearing by remitting bank.",
        },
        expected_facts=[
            ExpectedFact(field="clearing_date", expected_value=date(2026, 1, 14), data_type="DATE"),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Bank statement shows value date was Wednesday, proving broker credited ledger on same day funds were received."],
        ),
    ),
]
