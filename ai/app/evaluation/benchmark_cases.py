"""Ground-truth Gold Benchmark Cases for SANGYAN Provision Retrieval.

Epistemic foundation:
- Built strictly from actual verified provisions in PostgreSQL.
- Covers multiple authoritative bodies: SEBI, CDSL, NSDL.
- Covers multiple market intermediaries: Zerodha, Angel One, ICICI Direct, Upstox, Groww.
- Covers both substantive rules, fee schedules, procedural escalation matrices, and temporal regimes.
"""

from datetime import date
from pydantic import BaseModel, Field

from ai.app.retrieval.contracts import RetrievalMode, RetrievalQuery
from ai.app.sources.routing import KnowledgeDomain


class GoldBenchmarkCase(BaseModel):
    """Specification of a gold benchmark test case."""
    case_id: str
    description: str
    query: RetrievalQuery
    expected_provision_ids: list[str] = Field(description="Actual matching provision IDs in PostgreSQL.")
    expected_authorities: list[str] = Field(default_factory=list)
    expected_organisations: list[str] = Field(default_factory=list)
    expected_temporal_status: str | None = None
    expected_citation_substr: str | None = None


GOLD_BENCHMARK_CASES: list[GoldBenchmarkCase] = [
    # 1. Zerodha DP Charge Dispute
    GoldBenchmarkCase(
        case_id="GOLD-01",
        description="Investor sold shares through Zerodha and disputes DP charges on debit of securities from demat account.",
        query=RetrievalQuery(
            issue="Dispute over depository participant charges on debit of shares",
            issue_category="dp_charges",
            organisation_id="ORG_ZERODHA",
            disputed_action="DP charge deduction upon sale of equity delivery",
            issue_domains=[KnowledgeDomain.DP_CHARGES, KnowledgeDomain.BROKER],
            key_terms=["dp charges", "demat account", "zerodha charges", "debit"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_zerodha_591f5ecebb5b3fc3_sec_2_8c1525537d67",
            "prov_doc_org_org_zerodha_591f5ecebb5b3fc3_sec_3_7789c9e2b6e6",
            "prov_doc_org_org_zerodha_591f5ecebb5b3fc3_sec_5_5dd6c4f0156d",
            "prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_9_957d01daca9b",
            "prov_doc_org_org_zerodha_8ff8b5fc0f7960ca_sec_9_5d2d26dbc303",
        ],
        expected_authorities=["SEBI", "CDSL", "NSDL"],
        expected_organisations=["ORG_ZERODHA"],
    ),

    # 2. Angel One DP Charge Inquiry
    GoldBenchmarkCase(
        case_id="GOLD-02",
        description="Investor seeks clarification on Angel One DP charge of Rs 20 per scrip per day on trading.",
        query=RetrievalQuery(
            issue="Whether Angel One levies Rs 20 DP charge per scrip",
            issue_category="dp_charges",
            organisation_id="ORG_ANGELONE",
            issue_domains=[KnowledgeDomain.DP_CHARGES, KnowledgeDomain.BROKER],
            key_terms=["dp charge in trading", "rs 20 per scrip", "stock market"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_angelone_e6c7f9c9c4341582_sec_28_13f51f8cd117",
            "prov_doc_org_org_angelone_15f2261ebececfc3_sec_28_13f51f8cd117",
        ],
        expected_authorities=["SEBI", "CDSL", "NSDL"],
        expected_organisations=["ORG_ANGELONE"],
    ),

    # 3. Angel One Escalation Matrix & SCORES
    GoldBenchmarkCase(
        case_id="GOLD-03",
        description="Investor seeking grievance escalation procedure to SEBI SCORES for unresolved complaint against Angel One.",
        query=RetrievalQuery(
            issue="How to escalate unresolved complaint to SEBI SCORES portal",
            issue_category="grievance_escalation",
            organisation_id="ORG_ANGELONE",
            issue_domains=[KnowledgeDomain.GRIEVANCE_ESCALATION, KnowledgeDomain.SCORES],
            key_terms=["sebi scores", "complaint ref no", "escalation matrix", "exhausted"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_angelone_ab690e8e4cf2463b_sec_1_5a870aeb574d",
            "prov_doc_org_org_angelone_ab690e8e4cf2463b_sec_1_bb8497abb815",
            "prov_doc_org_org_angelone_c58069cfa2f3b78a_sec_1_5a870aeb574d",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_ANGELONE"],
    ),

    # 4. ICICI Direct Investment Adviser Escalation Matrix
    GoldBenchmarkCase(
        case_id="GOLD-04",
        description="Grievance escalation hierarchy for Investment Adviser services under ICICI Securities.",
        query=RetrievalQuery(
            issue="Escalation matrix contact persons for Investment Adviser complaints",
            issue_category="grievance_escalation",
            organisation_id="ORG_ICICIDIRECT",
            issue_domains=[KnowledgeDomain.GRIEVANCE_ESCALATION],
            key_terms=["escalation matrix", "investment adviser", "ia", "jeetu jawrani"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_icicidirect_6976eeb19a00e8e7_page_2_7ce19a8b7a20",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_ICICIDIRECT"],
    ),

    # 5. ICICI Direct Physical Delivery of F&O Contracts Brokerage
    GoldBenchmarkCase(
        case_id="GOLD-05",
        description="Brokerage charged on physical delivery settlement of F&O contracts by ICICI Direct.",
        query=RetrievalQuery(
            issue="Brokerage levied on physical delivery of F&O derivatives contracts",
            issue_category="brokerage",
            organisation_id="ORG_ICICIDIRECT",
            issue_domains=[KnowledgeDomain.BROKERAGE, KnowledgeDomain.TRADING],
            key_terms=["brokerage charged", "physical delivery", "f&o contracts"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_icicidirect_b4f6e3964e25cf44_sec_6_d9dae60e9e8d",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_ICICIDIRECT"],
    ),

    # 6. SEBI Standing Instructions for SIP in Demat Accounts
    GoldBenchmarkCase(
        case_id="GOLD-06",
        description="SEBI circular extending facility of creating standing instructions for Systematic Investment Plan (SIP) in demat accounts.",
        query=RetrievalQuery(
            issue="Facility of creating standing instructions for Systematic Investment Plan in demat mode",
            issue_category="dematerialisation",
            issue_domains=[KnowledgeDomain.DEMATERIALISATION, KnowledgeDomain.DEPOSITORY],
            target_authorities=["SEBI"],
            key_terms=["standing instructions", "systematic investment plan", "sip", "depositories"],
        ),
        expected_provision_ids=[
            "prov_doc_reg_sebi_0822d6895e61d08d_page_1_039018745ee3",
            "prov_doc_reg_sebi_0822d6895e61d08d_page_1_5102bad08872",
        ],
        expected_authorities=["SEBI"],
    ),

    # 7. SEBI Circular Force and Commencement Date
    GoldBenchmarkCase(
        case_id="GOLD-07",
        description="Immediate commencement date of SEBI circular provisions on mutual fund standing instructions.",
        query=RetrievalQuery(
            issue="When do the provisions of the circular come into force",
            issue_category="regulatory_effective_date",
            target_authorities=["SEBI"],
            target_citations=["provisions of this circular shall come into force with immediate"],
            issue_domains=[KnowledgeDomain.DEPOSITORY],
        ),
        expected_provision_ids=[
            "prov_doc_reg_sebi_0822d6895e61d08d_page_2_02136b32fce9",
        ],
        expected_authorities=["SEBI"],
    ),

    # 8. NSDL Investor Grievance Redressal Portal
    GoldBenchmarkCase(
        case_id="GOLD-08",
        description="NSDL investor portal for submitting complaints against depository participants.",
        query=RetrievalQuery(
            issue="Submitting grievance through NSDL investor grievance portal",
            issue_category="investor_grievance",
            target_authorities=["NSDL"],
            issue_domains=[KnowledgeDomain.INVESTOR_GRIEVANCE, KnowledgeDomain.DEPOSITORY],
            key_terms=["grievance redressal portal", "nsdl", "submit complaints"],
        ),
        expected_provision_ids=[
            "prov_doc_reg_nsdl_37fc29207b492f5f_sec_2_eea7a9a9ad1c",
        ],
        expected_authorities=["NSDL"],
    ),

    # 9. NSDL SCORES Escalation Platform
    GoldBenchmarkCase(
        case_id="GOLD-09",
        description="Lodging complaints through SEBI Complaints Redress System (SCORES) as referenced by NSDL.",
        query=RetrievalQuery(
            issue="Register complaints through SEBI SCORES platform from depository",
            issue_category="scores",
            target_authorities=["NSDL", "SEBI"],
            issue_domains=[KnowledgeDomain.INVESTOR_GRIEVANCE, KnowledgeDomain.SCORES],
            key_terms=["sebi complaints redress system", "scores", "register your complaints"],
        ),
        expected_provision_ids=[
            "prov_doc_reg_nsdl_37fc29207b492f5f_sec_19_aab7d29324e0",
        ],
        expected_authorities=["NSDL", "SEBI"],
    ),

    # 10. CDSL KYC Compliance Deadline
    GoldBenchmarkCase(
        case_id="GOLD-10",
        description="CDSL advisory on last date to update KYC compliance for demat account holders.",
        query=RetrievalQuery(
            issue="Deadline for KYC update compliance in demat account",
            issue_category="kyc",
            target_authorities=["CDSL"],
            issue_domains=[KnowledgeDomain.KYC, KnowledgeDomain.DEPOSITORY],
            key_terms=["last date to update kyc", "june 30 2022", "cdsl"],
        ),
        expected_provision_ids=[
            "prov_doc_reg_cdsl_b78236eb9090bedc_sec_3_a65157b112d7",
        ],
        expected_authorities=["CDSL"],
    ),

    # 11. Upstox GST on Brokerage and Demat Charges
    GoldBenchmarkCase(
        case_id="GOLD-11",
        description="Upstox tariff terms regarding 18% GST on brokerage and demat transaction charges.",
        query=RetrievalQuery(
            issue="Applicability of 18% GST on brokerage and demat charges",
            issue_category="brokerage",
            organisation_id="ORG_UPSTOX",
            issue_domains=[KnowledgeDomain.BROKERAGE, KnowledgeDomain.DP_CHARGES],
            key_terms=["18%", "brokerage", "demat charges", "ipft charges"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_upstox_f2afe8afaaac8c78_sec_17_a667135eb1c5",
        ],
        expected_authorities=["SEBI", "CDSL", "NSDL"],
        expected_organisations=["ORG_UPSTOX"],
    ),

    # 12. Zerodha Off-Market Securities Transfer Charges
    GoldBenchmarkCase(
        case_id="GOLD-12",
        description="Fees levied by Zerodha for off-market transfer of securities from demat account.",
        query=RetrievalQuery(
            issue="Charges for off-market transfer of securities",
            issue_category="demat_transfer",
            organisation_id="ORG_ZERODHA",
            issue_domains=[KnowledgeDomain.DEMAT_TRANSFER, KnowledgeDomain.DP_CHARGES],
            key_terms=["off-market transfer charges", "transfer"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_9_957d01daca9b",
            "prov_doc_org_org_zerodha_8ff8b5fc0f7960ca_sec_9_957d01daca9b",
        ],
        expected_authorities=["SEBI", "CDSL", "NSDL"],
        expected_organisations=["ORG_ZERODHA"],
    ),

    # 13. Zerodha Demat and Trading Account Opening
    GoldBenchmarkCase(
        case_id="GOLD-13",
        description="Terms governing opening of demat account and trading account with Zerodha.",
        query=RetrievalQuery(
            issue="Opening demat account and trading account terms",
            issue_category="broker",
            organisation_id="ORG_ZERODHA",
            issue_domains=[KnowledgeDomain.BROKER, KnowledgeDomain.DEPOSITORY],
            key_terms=["demat account", "opening an account with zerodha", "trading account"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_zerodha_591f5ecebb5b3fc3_sec_3_7789c9e2b6e6",
        ],
        expected_authorities=["SEBI", "CDSL", "NSDL"],
        expected_organisations=["ORG_ZERODHA"],
    ),

    # 14. Groww Customer Support FAQs
    GoldBenchmarkCase(
        case_id="GOLD-14",
        description="Groww customer support portal for most asked questions and grievance guidance.",
        query=RetrievalQuery(
            issue="Accessing Groww customer support help and FAQs",
            issue_category="investor_grievance",
            organisation_id="ORG_GROWW",
            issue_domains=[KnowledgeDomain.INVESTOR_GRIEVANCE, KnowledgeDomain.BROKER],
            key_terms=["customer support", "most asked questions", "faqs"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_groww_2a1d9c223b9d744b_sec_root_2ad8c084fb17",
            "prov_doc_org_org_groww_011e4cd915707471_sec_root_2ad8c084fb17",
            "prov_doc_org_org_groww_2a1d9c223b9d744b_sec_root_43bd27caccdd",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_GROWW"],
    ),

    # 15. Angel One Exchange Transaction Charges Schedule
    GoldBenchmarkCase(
        case_id="GOLD-15",
        description="Exchange transaction charges levied on equity transactions by Angel One.",
        query=RetrievalQuery(
            issue="Schedule of exchange transaction charges",
            issue_category="brokerage",
            organisation_id="ORG_ANGELONE",
            issue_domains=[KnowledgeDomain.TRADING, KnowledgeDomain.BROKERAGE],
            key_terms=["exchange transaction charges", "turnover"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_angelone_e6c7f9c9c4341582_sec_1_0d44ed915294",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_ANGELONE"],
    ),

    # 16. Angel One Discount Brokerage Structure
    GoldBenchmarkCase(
        case_id="GOLD-16",
        description="Angel One policy statement on discount brokerage services.",
        query=RetrievalQuery(
            issue="Discount brokerage model and charges offered by Angel One",
            issue_category="brokerage",
            organisation_id="ORG_ANGELONE",
            issue_domains=[KnowledgeDomain.BROKERAGE],
            key_terms=["full-service discount broker", "angel one", "offer"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_angelone_e6c7f9c9c4341582_sec_17_ce782de19337",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_ANGELONE"],
    ),

    # 17. SEBI Statutory Authority Conferred Under SEBI Act
    GoldBenchmarkCase(
        case_id="GOLD-17",
        description="Legal authority under Section 11(1) of SEBI Act and Section 19 of Depositories Act.",
        query=RetrievalQuery(
            issue="Exercise of powers conferred under Section 11(1) of SEBI Act",
            issue_category="regulatory_power",
            target_authorities=["SEBI"],
            target_citations=["exercise of powers conferred under Section 11"],
            issue_domains=[KnowledgeDomain.DEPOSITORY],
        ),
        expected_provision_ids=[
            "prov_doc_reg_sebi_0822d6895e61d08d_page_2_d78a308352ca",
        ],
        expected_authorities=["SEBI"],
    ),

    # 18. Zerodha Brokerage Calculator & Upfront Costs
    GoldBenchmarkCase(
        case_id="GOLD-18",
        description="Zerodha policy directing clients to upfront brokerage calculator.",
        query=RetrievalQuery(
            issue="Calculating upfront transaction costs using brokerage calculator",
            issue_category="brokerage",
            organisation_id="ORG_ZERODHA",
            issue_domains=[KnowledgeDomain.BROKERAGE],
            key_terms=["calculate your costs upfront", "brokerage calculator"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_7_ae896e093bc8",
            "prov_doc_org_org_zerodha_8ff8b5fc0f7960ca_sec_7_ae896e093bc8",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_ZERODHA"],
    ),

    # 19. Zerodha Charges Schedule Page Reference
    GoldBenchmarkCase(
        case_id="GOLD-19",
        description="Zerodha policy referencing updated charge list and tariff schedule.",
        query=RetrievalQuery(
            issue="Reference to updated charge list in Zerodha policies",
            issue_category="brokerage",
            organisation_id="ORG_ZERODHA",
            issue_domains=[KnowledgeDomain.BROKERAGE, KnowledgeDomain.DP_CHARGES],
            key_terms=["zerodha charges", "updated charge list"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_zerodha_591f5ecebb5b3fc3_sec_4_d25914b8e238",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_ZERODHA"],
    ),

    # 20. NSDL One-Stop Platform for Investor Queries
    GoldBenchmarkCase(
        case_id="GOLD-20",
        description="NSDL charter statement providing one-stop platform for investor grievances.",
        query=RetrievalQuery(
            issue="One stop platform for investors to seek redressal of queries",
            issue_category="investor_grievance",
            target_authorities=["NSDL"],
            issue_domains=[KnowledgeDomain.INVESTOR_GRIEVANCE, KnowledgeDomain.DEPOSITORY],
            key_terms=["one stop platform", "redressal of their queries"],
        ),
        expected_provision_ids=[
            "prov_doc_reg_nsdl_37fc29207b492f5f_sec_1_3887a928a94e",
        ],
        expected_authorities=["NSDL"],
    ),

    # 21. Historical Incident with KYC Deadline
    GoldBenchmarkCase(
        case_id="GOLD-21",
        description="Historical incident in 2021 regarding KYC update deadline (June 30, 2022).",
        query=RetrievalQuery(
            issue="Advisory on updating KYC on or before June 30 2022",
            issue_category="kyc",
            target_authorities=["CDSL"],
            mode=RetrievalMode.HISTORICAL_RULES,
            incident_date=date(2021, 10, 1),
            issue_domains=[KnowledgeDomain.KYC, KnowledgeDomain.DEPOSITORY],
            key_terms=["update kyc", "june 30 2022"],
        ),
        expected_provision_ids=[
            "prov_doc_reg_cdsl_b78236eb9090bedc_sec_3_a65157b112d7",
        ],
        expected_authorities=["CDSL"],
    ),

    # 22. Future Unresolved Incident Date for Mutual Fund Standing Instructions
    GoldBenchmarkCase(
        case_id="GOLD-22",
        description="Incident with unresolved incident date for mutual fund standing instructions circular.",
        query=RetrievalQuery(
            issue="Standing instructions for Systematic Investment Plan in demat mode",
            issue_category="dematerialisation",
            target_authorities=["SEBI"],
            issue_domains=[KnowledgeDomain.DEMATERIALISATION],
            key_terms=["standing instructions", "mutual fund", "sip"],
        ),
        expected_provision_ids=[
            "prov_doc_reg_sebi_0822d6895e61d08d_page_1_039018745ee3",
        ],
        expected_authorities=["SEBI"],
    ),

    # 23. Cross-Organisation Brokerage Query (Zerodha vs Market)
    GoldBenchmarkCase(
        case_id="GOLD-23",
        description="Inquiry on Zerodha NRI brokerage schedule.",
        query=RetrievalQuery(
            issue="NRI brokerage charges levied by Zerodha",
            issue_category="brokerage",
            organisation_id="ORG_ZERODHA",
            issue_domains=[KnowledgeDomain.BROKERAGE],
            key_terms=["nri brokerage charges", "brokerage"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_zerodha_fff0bf49a674ef5d_sec_9_200cee0d8b84",
            "prov_doc_org_org_zerodha_8ff8b5fc0f7960ca_sec_9_200cee0d8b84",
            "prov_doc_org_org_zerodha_591f5ecebb5b3fc3_sec_4_d25914b8e238",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_ZERODHA"],
    ),

    # 24. SEBI Direction to Jointly Publish SOP
    GoldBenchmarkCase(
        case_id="GOLD-24",
        description="SEBI direction requiring Depositories to jointly publish standard operating procedure (SOP).",
        query=RetrievalQuery(
            issue="Depositories directed to jointly publish standard operating procedure",
            issue_category="depository",
            target_authorities=["SEBI"],
            issue_domains=[KnowledgeDomain.DEPOSITORY],
            key_terms=["jointly publish", "standard operating procedure", "sop"],
        ),
        expected_provision_ids=[
            "prov_doc_reg_sebi_0822d6895e61d08d_page_2_c0cdf5785d8d",
        ],
        expected_authorities=["SEBI"],
    ),

    # 25. ICICI Direct Registered Office & Compliance Details
    GoldBenchmarkCase(
        case_id="GOLD-25",
        description="Registration numbers and compliance details of ICICI Securities registered office.",
        query=RetrievalQuery(
            issue="ICICI Securities registered office details and SEBI registration numbers",
            issue_category="investor_grievance",
            organisation_id="ORG_ICICIDIRECT",
            issue_domains=[KnowledgeDomain.INVESTOR_GRIEVANCE],
            key_terms=["registered office details", "inz000183631", "ina000000094"],
        ),
        expected_provision_ids=[
            "prov_doc_org_org_icicidirect_6976eeb19a00e8e7_page_1_1dec99b4f88d",
        ],
        expected_authorities=["SEBI"],
        expected_organisations=["ORG_ICICIDIRECT"],
    ),
]
