"""Retrieval Query Planner for SANGYAN Grievance Retrieval.

Epistemic foundation:
- Translates CaseSemanticRepresentation into 1..N targeted, structured retrieval queries.
- Multi-query strategy provides diverse semantic entry points into PostgreSQL/pgvector:
  1. PRIMARY_ISSUE: Specific organisation + primary grievance terms.
  2. CHARGE_OR_TRANSACTION: Substantive operational charge description.
  3. REGULATORY_CONCEPT: Depository and regulatory framework rules (SEBI/CDSL/NSDL).
  4. ORGANISATION_POLICY: Official intermediary schedule of charges / tariff sheet.
- Structured constraints: Propagates target organisation ID to prevent cross-broker leakage.
"""

import logging
from typing import Sequence
import uuid

from ai.app.retrieval.contracts import RetrievalMode, RetrievalQuery
from ai.app.sources.routing import KnowledgeDomain
from ai.app.understanding.contracts import (
    CaseSemanticRepresentation,
    PlannedQuery,
    QueryType,
)
from ai.app.understanding.taxonomy import IssueDomainConcept

logger = logging.getLogger("sangyan.understanding.query_planner")


class RetrievalQueryPlanner:
    """Generates structured, multi-angle retrieval queries from semantic case representations."""

    @classmethod
    def plan_queries(cls, sem: CaseSemanticRepresentation) -> list[PlannedQuery]:
        """Generate structured complementary queries for hybrid retrieval."""
        queries: list[PlannedQuery] = []
        org_id = sem.organisation_id
        org_label = sem.organisation or (org_id.replace("ORG_", "").title() if org_id else "")
        target_auths = [sem.authority] if sem.authority else ["SEBI", "CDSL", "NSDL"]

        # Helper to generate unique ID
        def _qid(prefix: str) -> str:
            return f"QRY-{prefix}-{uuid.uuid4().hex[:6]}"

        # -------------------------------------------------------------
        # 1. PRIMARY_ISSUE Query
        # -------------------------------------------------------------
        primary_parts = []
        if org_label:
            primary_parts.append(org_label)
        if sem.charge_type:
            primary_parts.append(sem.charge_type.replace("_", " "))
        elif sem.issue_type and sem.issue_type != IssueDomainConcept.UNKNOWN_CONCEPT.value:
            primary_parts.append(sem.issue_type.replace("_", " "))
        elif sem.transaction_type:
            primary_parts.append(sem.transaction_type.replace("_", " "))
        elif sem.raw_text:
            # Fallback to key terms from raw text (first 80 chars)
            primary_parts.append(sem.raw_text[:80])

        primary_text = " ".join(primary_parts).strip()
        if primary_text:
            queries.append(
                PlannedQuery(
                    query_id=_qid("PRIM"),
                    query_text=primary_text,
                    query_type=QueryType.PRIMARY_ISSUE,
                    target_organisation=org_id,
                    target_authorities=target_auths,
                    key_terms=sem.retrieval_concepts,
                    incident_date=sem.incident_date,
                    reference_date=sem.reference_date,
                    weight=1.0,
                )
            )

        # -------------------------------------------------------------
        # 2. CHARGE_OR_TRANSACTION Query (Substantive operational terms)
        # -------------------------------------------------------------
        if sem.charge_type == "dp_charges" or "dp" in sem.raw_text.lower():
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="What is DP charge for trading in the stock market sell side per scrip",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["CDSL", "NSDL", "SEBI"],
                    key_terms=["dp charges", "demat debit", "equity delivery sell"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.charge_type == "annual_maintenance_charge" or "amc" in sem.raw_text.lower():
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="annual maintenance charge AMC fee demat account BSDA",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["SEBI", "CDSL", "NSDL"],
                    key_terms=["amc", "maintenance charge", "bsda"],
                    incident_date=sem.incident_date,
                    weight=0.9,
                )
            )
        elif sem.transaction_type == "intraday_equity":
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="intraday equity brokerage charge flat fee turnover",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["SEBI"],
                    key_terms=["intraday", "brokerage"],
                    incident_date=sem.incident_date,
                    weight=0.9,
                )
            )
        elif sem.action == "margin_pledge_creation" or sem.charge_type == "margin_pledge_fee":
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="margin pledge creation fee charges depository",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["CDSL", "NSDL", "SEBI"],
                    key_terms=["pledge", "margin pledge fee"],
                    incident_date=sem.incident_date,
                    weight=0.9,
                )
            )
        elif sem.charge_type == "call_and_trade_fee" or sem.order_channel == "phone_call_and_trade":
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="call and trade charges phone orders customer desk",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["SEBI"],
                    key_terms=["call and trade", "phone order"],
                    incident_date=sem.incident_date,
                    weight=0.9,
                )
            )
        elif sem.charge_type == "payment_gateway_fee" or sem.payment_mode == "UPI":
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="payment gateway charges adding funds net banking UPI",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["SEBI"],
                    key_terms=["payment gateway", "adding funds", "UPI"],
                    incident_date=sem.incident_date,
                    weight=0.9,
                )
            )
        elif sem.charge_type == "mtf_interest" or sem.product == "MTF":
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="MTF margin trading facility interest rate per day delayed payment",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["SEBI"],
                    key_terms=["MTF", "margin trading facility", "interest"],
                    incident_date=sem.incident_date,
                    weight=0.9,
                )
            )
        elif sem.process == "account_opening":
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="charges for opening a new demat and trading account fee schedule",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["SEBI"],
                    key_terms=["account opening", "free demat"],
                    incident_date=sem.incident_date,
                    weight=0.9,
                )
            )
        elif sem.process == "direct_mutual_fund" or sem.product_type == "direct_mutual_fund":
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="direct mutual funds investment transaction fee commission charges",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["SEBI"],
                    key_terms=["direct mutual fund", "commission"],
                    incident_date=sem.incident_date,
                    weight=0.9,
                )
            )
        elif sem.charge_type == "brokerage":
            queries.append(
                PlannedQuery(
                    query_id=_qid("CHRG"),
                    query_text="brokerage charges equity delivery trading zero brokerage tariff",
                    query_type=QueryType.CHARGE_OR_TRANSACTION,
                    target_organisation=org_id,
                    target_authorities=["SEBI"],
                    key_terms=["brokerage", "equity delivery"],
                    incident_date=sem.incident_date,
                    weight=0.9,
                )
            )

        # -------------------------------------------------------------
        # 3. REGULATORY_CONCEPT Query (Depository & Regulatory Rules)
        # -------------------------------------------------------------
        if sem.portal == "SEBI_SCORES":
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text="SEBI SCORES statutory timeline grievance redressal 21 calendar days",
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=["SEBI"],
                    key_terms=["scores", "grievance timeline"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.authority in ("NSDL", "CDSL"):
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text=f"{sem.authority} depository escalation hierarchy grievance resolution",
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=[sem.authority, "SEBI"],
                    key_terms=["escalation matrix", "depository"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.process == "contract_note":
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text="SEBI master circular ECN electronic contract note within 24 hours",
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=["SEBI"],
                    key_terms=["electronic contract note", "ECN", "24 hours"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.process == "statement_of_holdings":
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text="statement of holdings transaction statement quarterly periodic depository CDSL NSDL",
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=["CDSL", "NSDL", "SEBI"],
                    key_terms=["statement of holding", "quarterly statement"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.process == "ddpi_poa":
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text="SEBI circular execution of DDPI power of attorney demat debit client securities",
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=["SEBI"],
                    key_terms=["power of attorney", "DDPI", "POA"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.process == "direct_payout":
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text="SEBI circular direct payout of securities to client demat account pool account",
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=["SEBI", "CDSL", "NSDL"],
                    key_terms=["direct payout", "pool account retention"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.process == "peak_margin":
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text="SEBI circular peak margin collection penalty upfront margin reporting",
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=["SEBI"],
                    key_terms=["peak margin penalty", "upfront margin"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.action == "ipo_application":
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text="SEBI circular UPI mechanism in public issues limit 5 lakh",
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=["SEBI"],
                    key_terms=["IPO UPI limit", "public issues"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.action == "unauthorized_trade":
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text="SEBI circular unauthorized trades dispute mechanism reporting within 24 hours",
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=["SEBI"],
                    key_terms=["unauthorized trade", "dispute mechanism"],
                    incident_date=sem.incident_date,
                    weight=0.95,
                )
            )
        elif sem.regulatory_concepts:
            reg_text = " ".join(sem.regulatory_concepts)
            queries.append(
                PlannedQuery(
                    query_id=_qid("REG"),
                    query_text=reg_text,
                    query_type=QueryType.REGULATORY_CONCEPT,
                    target_authorities=["SEBI", "CDSL", "NSDL"],
                    key_terms=sem.regulatory_concepts,
                    incident_date=sem.incident_date,
                    weight=0.85,
                )
            )

        # -------------------------------------------------------------
        # 4. ORGANISATION_POLICY Query (Intermediary Tariff Sheet)
        # -------------------------------------------------------------
        if org_id:
            queries.append(
                PlannedQuery(
                    query_id=_qid("POL"),
                    query_text=f"{org_label} charges explained fee schedule tariff sheet",
                    query_type=QueryType.ORGANISATION_POLICY,
                    target_organisation=org_id,
                    key_terms=["tariff sheet", "charges explained"],
                    incident_date=sem.incident_date,
                    weight=0.85,
                )
            )

        # Deduplicate planned queries by query_text
        seen_texts: set[str] = set()
        deduped_queries: list[PlannedQuery] = []
        for q in queries:
            norm_q = q.query_text.strip().lower()
            if norm_q not in seen_texts:
                seen_texts.add(norm_q)
                deduped_queries.append(q)

        return deduped_queries

    @classmethod
    def to_retrieval_query(cls, planned: PlannedQuery) -> RetrievalQuery:
        """Convert an internal PlannedQuery into the retriever's contract RetrievalQuery."""
        mode = RetrievalMode.HISTORICAL_RULES if planned.incident_date else RetrievalMode.CURRENT_RULES
        domains = []
        if "dp" in planned.query_text.lower():
            domains.extend([KnowledgeDomain.DP_CHARGES, KnowledgeDomain.DEPOSITORY])
        if "brokerage" in planned.query_text.lower() or "intraday" in planned.query_text.lower():
            domains.extend([KnowledgeDomain.BROKER, KnowledgeDomain.TRADING])
        if "amc" in planned.query_text.lower():
            domains.extend([KnowledgeDomain.AMC, KnowledgeDomain.DEPOSITORY])
        if "pledge" in planned.query_text.lower():
            domains.extend([KnowledgeDomain.PLEDGE, KnowledgeDomain.DEPOSITORY])
        if "scores" in planned.query_text.lower():
            domains.extend([KnowledgeDomain.SCORES, KnowledgeDomain.INVESTOR_GRIEVANCE])

        return RetrievalQuery(
            query_text=planned.query_text,
            organisation_id=planned.target_organisation,
            target_authorities=planned.target_authorities,
            key_terms=planned.key_terms,
            incident_date=planned.incident_date,
            reference_date=planned.reference_date or planned.incident_date,
            mode=mode,
            issue_domains=list(set(domains)),
            top_k=10,
        )
