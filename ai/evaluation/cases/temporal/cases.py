"""Temporal Regime Benchmark Cases (L5) for SANGYAN Evaluation (Phase 7A).

Epistemic foundation:
- 10 cases testing temporal validity, historical amendments, and superseded circular traps.
- Evaluates whether the operative rule is selected based on transaction_date, NOT the newest circular date.
- Tests BSDA threshold expansion, T+1 settlement migration, SCORES 2.0, and DDPI transition.
"""

from datetime import date
from decimal import Decimal

from ai.app.assessment.contracts import AssessmentStatus
from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedAssessment,
    ExpectedFact,
    ExpectedIssue,
    ExpectedProvision,
    ExpectedTemporalContext,
)
from ai.evaluation.corpus.taxonomy import (
    AdversarialSubtype,
    CaseCategory,
    CaseVisibility,
    DifficultyLevel,
    RetrievalRelevance,
)

CASES: list[EvaluationCase] = [
    # 1. BSDA Pre-Amendment (Holding ₹3.5L in April 2024 -> AMC Applicable)
    EvaluationCase(
        case_id="TEMP-001",
        title="BSDA threshold dispute under pre-September 2024 regime (Limit ₹2 Lakh)",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="ICICI Direct charged me Rs 300 AMC on 2024-04-15 for my BSDA demat account. My portfolio was worth Rs 3,50,000. Under SEBI rules BSDA is free up to 10 lakhs! Refund my money.",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ICICIDIRECT", required=True),
            ExpectedFact(field="transaction_date", expected_value=date(2024, 4, 15), data_type="DATE", required=True),
            ExpectedFact(field="portfolio_value", expected_value=Decimal("350000.00"), data_type="DECIMAL"),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            transaction_date=date(2024, 4, 15),
            expected_rule_version="SEBI_CIR_BSDA_2012_OLD",
            is_superseded_at_transaction_date=False,
            applicable_circular_ref="CIR/MRD/DP/20/2012 (Threshold: Rs 2,00,000)",
        ),
        expected_issues=ExpectedIssue(
            primary_issue="Applicability of BSDA zero-AMC ceiling prior to September 1, 2024 revision",
            secondary_issues=["Historical circular regime applicability"],
            irrelevant_plausible_issues=["New BSDA 10 lakh ceiling effective Sep 2024"],
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_org_org_icicidirect_6976eeb19a00e8e7_page_1_1dec99b4f88d",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Under the 2012 BSDA circular applicable on 2024-04-15, portfolio above Rs 2,00,000 was subject to regular AMC.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["On 2024-04-15, the BSDA threshold was Rs 2,00,000. Holding of Rs 3.5L exceeded threshold, making AMC lawful."],
            provenance_notes="User retroactively applies the 2024 amendment which only took effect on 2024-09-01.",
        ),
    ),

    # 2. BSDA Post-Amendment (Holding ₹3.5L in October 2024 -> Zero AMC Mandated)
    EvaluationCase(
        case_id="TEMP-002",
        title="BSDA threshold dispute post-September 2024 revision (Limit ₹10 Lakh)",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="Angel One deducted Rs 300 AMC on 2024-10-15 on my BSDA account holding Rs 3,50,000 worth of shares. Is this allowed?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ANGELONE", required=True),
            ExpectedFact(field="transaction_date", expected_value=date(2024, 10, 15), data_type="DATE", required=True),
            ExpectedFact(field="portfolio_value", expected_value=Decimal("350000.00"), data_type="DECIMAL"),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            transaction_date=date(2024, 10, 15),
            expected_rule_version="SEBI_CIR_BSDA_2024_REVISED",
            is_superseded_at_transaction_date=False,
            applicable_circular_ref="SEBI Circular SEBI/HO/MIRSD/POD-1/P/CIR/2024/91 (Effective Sep 1, 2024)",
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_cdsl_b78236eb9090bedc_sec_3_a65157b112d7",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI BSDA Circular 2024/91 mandates zero AMC for demat portfolio holdings up to Rs 4 Lakh.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["Under revised SEBI BSDA circular effective 2024-09-01, holdings up to Rs 4,00,000 incur zero AMC."],
            expected_violations=["Violation of revised BSDA fee schedule under SEBI Circular 2024/91."],
        ),
    ),

    # 3. Peak Margin Phase 2 (50% Upfront Margin in Jan 2021)
    EvaluationCase(
        case_id="TEMP-003",
        title="Peak margin shortfall penalty under Phase 2 (50% threshold)",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="My broker levied peak margin penalty on 2021-01-20 because I only had 60% margin available. But 100% was not required then!",
        expected_facts=[
            ExpectedFact(field="transaction_date", expected_value=date(2021, 1, 20), data_type="DATE", required=True),
            ExpectedFact(field="margin_available_pct", expected_value=Decimal("60.00"), data_type="DECIMAL"),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            transaction_date=date(2021, 1, 20),
            expected_rule_version="PEAK_MARGIN_PHASE_2",
            applicable_circular_ref="SEBI Peak Margin Circular (Phase 2: 50% upfront requirement)",
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_page_18_8cf99e05aec0",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI peak margin framework phased circular mandated 50% upfront margin in Phase 2.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["In January 2021 (Phase 2), required peak margin was 50%. Client had 60%, so no penalty was leviable."],
            expected_violations=["Improper peak margin shortfall penalty levied when client met Phase 2 requirement."],
        ),
    ),

    # 4. T+2 Settlement Era Dispute
    EvaluationCase(
        case_id="TEMP-004",
        title="Settlement cycle dispute under historical T+2 regime",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="I sold shares on Tuesday 2022-06-14 and payout was made on Thursday 2022-06-16. Did the broker delay payout?",
        expected_facts=[
            ExpectedFact(field="transaction_date", expected_value=date(2022, 6, 14), data_type="DATE", required=True),
            ExpectedFact(field="settlement_date", expected_value=date(2022, 6, 16), data_type="DATE"),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            transaction_date=date(2022, 6, 14),
            expected_rule_version="SETTLEMENT_T_PLUS_2",
            applicable_circular_ref="SEBI T+2 Settlement Framework (prior to complete T+1 rollout)",
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Under applicable T+2 settlement regime in June 2022, Thursday settlement was timely and compliant."],
        ),
    ),

    # 5. SCORES 2.0 Complaint Redressal Process
    EvaluationCase(
        case_id="TEMP-005",
        title="SCORES 2.0 21-calendar-day revised timeline applicability",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="I filed a complaint on SCORES on 2024-07-01. The broker took 28 days to reply. Under SCORES 2.0 is this permitted?",
        expected_facts=[
            ExpectedFact(field="complaint_date", expected_value=date(2024, 7, 1), data_type="DATE", required=True),
            ExpectedFact(field="response_days", expected_value=28, data_type="INTEGER"),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            complaint_date=date(2024, 7, 1),
            expected_rule_version="SCORES_2_POINT_0",
            applicable_circular_ref="SEBI Circular on SCORES 2.0 (Effective April 1, 2024)",
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_page_15_2a0bf157af2e",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI SCORES 2.0 circular mandates 21 calendar day resolution window for market entities.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["Under SCORES 2.0 effective April 2024, designated entities must resolve complaints within 21 calendar days."],
            expected_violations=["Violation of SCORES 2.0 21-day statutory timeline."],
        ),
    ),

    # 6. DDPI Mandate Replacing POA
    EvaluationCase(
        case_id="TEMP-006",
        title="Demat Debit and Pledge Instruction (DDPI) mandatory cutoff",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="Broker forced me to sign a full physical Power of Attorney (POA) for demat operations in January 2024.",
        expected_facts=[
            ExpectedFact(field="transaction_date", expected_value=date(2024, 1, 10), data_type="DATE", required=True),
            ExpectedFact(field="document_demanded", expected_value="full_poa", required=True),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            transaction_date=date(2024, 1, 10),
            expected_rule_version="DDPI_FRAMEWORK_2022",
            applicable_circular_ref="SEBI DDPI Circular SEBI/HO/MIRSD/DoP/P/CIR/2022/44 (Mandatory post Nov 2022)",
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_page_18_b378fcf99c73",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI circular SEBI/HO/MIRSD/DoP/P/CIR/2022/44 prohibited blanket POAs and mandated DDPI post-November 2022.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["Post November 2022, brokers cannot mandate blanket POA; DDPI with limited 4-point scope is mandatory."],
            expected_violations=["Violation of SEBI circular replacing POA with DDPI."],
        ),
    ),

    # 7. SEBI Turnover Fee Historical Rate
    EvaluationCase(
        case_id="TEMP-007",
        title="SEBI regulatory turnover fee historical rate verification",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="My broker charged SEBI turnover fees on my trades on 2026-01-10. What is the currently applicable rate?",
        expected_facts=[
            ExpectedFact(field="transaction_date", expected_value=date(2026, 1, 10), data_type="DATE", required=True),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            transaction_date=date(2026, 1, 10),
            expected_rule_version="SEBI_TURNOVER_FEE_CURRENT",
            applicable_circular_ref="Rs 10 per crore (0.0001%)",
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["SEBI regulatory fee is currently Rs 10 per crore (0.0001% of traded value)."],
        ),
    ),

    # 8. STT Rate Hike on Options (October 1, 2024)
    EvaluationCase(
        case_id="TEMP-008",
        title="STT rate revision on options sale post-October 2024",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="Zerodha deducted STT of 0.1% on options premium sold on 2024-10-10. Previously it was 0.0625%! Did they overcharge?",
        expected_facts=[
            ExpectedFact(field="organisation", expected_value="ORG_ZERODHA", required=True),
            ExpectedFact(field="transaction_date", expected_value=date(2024, 10, 10), data_type="DATE", required=True),
            ExpectedFact(field="stt_rate", expected_value=Decimal("0.1"), data_type="DECIMAL"),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            transaction_date=date(2024, 10, 10),
            expected_rule_version="FINANCE_ACT_2024_STT",
            applicable_circular_ref="Finance Act (No. 2) 2024 effective October 1, 2024 (STT on option sale raised to 0.1%)",
        ),
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
            expected_findings=["Under Finance Act 2024, STT on sale of options was increased to 0.1% effective October 1, 2024."],
        ),
    ),

    # 9. Retail IPO UPI Limit (₹5 Lakh post-2022)
    EvaluationCase(
        case_id="TEMP-009",
        title="Retail IPO application UPI limit (₹5 Lakh regime)",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="Bank rejected my IPO application of Rs 3,50,000 via UPI on 2024-03-05 citing a Rs 2 lakh cap.",
        expected_facts=[
            ExpectedFact(field="transaction_date", expected_value=date(2024, 3, 5), data_type="DATE", required=True),
            ExpectedFact(field="application_amount", expected_value=Decimal("350000.00"), data_type="DECIMAL"),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            transaction_date=date(2024, 3, 5),
            expected_rule_version="SEBI_IPO_UPI_5_LAKH",
            applicable_circular_ref="SEBI Circular SEBI/HO/CFD/DIL2/CIR/P/2022/45 (Limit increased to Rs 5 Lakh)",
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_sebi_1fa7fdbd6f70d052_page_27_9ff5a7225d5e",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI circular SEBI/HO/CFD/DIL2/CIR/P/2022/45 raised retail individual investor IPO UPI limit to Rs 5 Lakh.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["UPI limit for IPO applications by retail individual investors was increased to Rs 5 lakh in May 2022."],
            expected_violations=["Improper rejection of IPO UPI mandate within statutory Rs 5 lakh limit."],
        ),
    ),

    # 10. Direct Payout of Securities to Client Demat (2024)
    EvaluationCase(
        case_id="TEMP-010",
        title="Direct payout of securities from clearing corporation to demat account",
        category=CaseCategory.TEMPORAL,
        difficulty=DifficultyLevel.L5,
        adversarial_subtype=AdversarialSubtype.HISTORICAL_TRAP,
        visibility=CaseVisibility.PUBLIC,
        user_input="Broker retained bought payout shares in their pool account instead of direct transfer to my demat in December 2024.",
        expected_facts=[
            ExpectedFact(field="transaction_date", expected_value=date(2024, 12, 10), data_type="DATE", required=True),
        ],
        expected_temporal_context=ExpectedTemporalContext(
            transaction_date=date(2024, 12, 10),
            expected_rule_version="DIRECT_PAYOUT_SECURITIES_2024",
            applicable_circular_ref="SEBI Circular on Direct Payout of Securities to Client Demat Account",
        ),
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_doc_reg_cdsl_b78236eb9090bedc_sec_1_61a12f8b25cb",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="SEBI direct payout of securities circular mandates clearing corporations credit client demat accounts directly.",
            ),
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.VIOLATION_CONFIRMED,
            expected_findings=["Under direct payout mandate, clearing corporations transfer bought securities directly to client demat."],
            expected_violations=["Violation of mandatory direct payout mechanism."],
        ),
    ),
]
