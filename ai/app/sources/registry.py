"""Official Source Registry for SANGYAN knowledge acquisition.

The registry is the single source of truth for WHERE knowledge may be acquired from.
Pre-populated with authoritative regulatory bodies (SEBI, NSE, BSE, CDSL, NSDL)
and registered market intermediary portals.
"""

from datetime import datetime, timezone
from typing import Sequence
from pydantic import HttpUrl

from ai.app.knowledge.source_classes import SourceClass
from ai.app.sources.models import (
    DiscoveryMethod,
    RefreshPolicy,
    SourceRegistryEntry,
    SourceStatus,
)


DEFAULT_OFFICIAL_SOURCES: list[SourceRegistryEntry] = [
    # --- SEBI (Statutory Apex Regulator) ---
    SourceRegistryEntry(
        source_id="sebi_cir_jagrook_investor_awareness_2026",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1790852162769.pdf"),
        expected_domain="sebi.gov.in",
        document_type="circular",
        topic=["stock_broker", "investor_grievance", "investor_awareness"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="SEBI Circular on Display of investor awareness message(s) by stock brokers under Project Jagrook.",
    ),
    SourceRegistryEntry(
        source_id="sebi_cir_transmission_securities_2026",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://www.sebi.gov.in/sebi_data/attachdocs/jul-2026/1784869499027.pdf"),
        expected_domain="sebi.gov.in",
        document_type="circular",
        topic=["securities_transfer", "investor_rights", "demat_transfer"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="SEBI Circular on Simplification and standardisation of framework for transmission of securities.",
    ),
    SourceRegistryEntry(
        source_id="sebi_cir_mf_demat_standing_instructions_2026",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://www.sebi.gov.in/sebi_data/attachdocs/jul-2026/1784285542603.pdf"),
        expected_domain="sebi.gov.in",
        document_type="circular",
        topic=["demat_transfer", "depository", "mutual_funds"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="SEBI Circular on Standing instructions for SWP/STP for Mutual Fund units held in demat form.",
    ),

    # --- NSE (Stock Exchange) ---
    SourceRegistryEntry(
        source_id="nse_investor_grievance_rules",
        authority="NSE",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://www.nseindia.com/invest/investor-grievance-redressal-mechanism"),
        expected_domain="nseindia.com",
        document_type="exchange_procedure",
        topic=["investor_grievance", "trading", "stock_exchange"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="NSE Investor Grievance Redressal Mechanism and Arbitration guidelines.",
    ),

    # --- BSE (Stock Exchange) ---
    SourceRegistryEntry(
        source_id="bse_investor_services",
        authority="BSE",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://www.bseindia.com/investors/invservices"),
        expected_domain="bseindia.com",
        document_type="exchange_procedure",
        topic=["investor_grievance", "stock_exchange"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="BSE Investor Services Cell procedures and complaint lodging guidelines.",
    ),

    # --- CDSL (Depository) ---
    SourceRegistryEntry(
        source_id="cdsl_investor_corner",
        authority="CDSL",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://www.cdslindia.com/eservices/Investors/InvestorCorner"),
        expected_domain="cdslindia.com",
        document_type="depository_procedure",
        topic=["depository", "demat_transfer", "dp_charges", "investor_grievance"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="CDSL Investor Corner: DP Tariffs, Grievance handling, and pending demat instructions.",
    ),
    SourceRegistryEntry(
        source_id="cdsl_demat_operating_instructions",
        authority="CDSL",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://www.cdslindia.com/Investors/open-demat.html"),
        expected_domain="cdslindia.com",
        document_type="depository_procedure",
        topic=["depository", "demat_transfer"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="CDSL Official Demat Account Operating Instructions and Investor Guidelines.",
    ),

    # --- NSDL (Depository) ---
    SourceRegistryEntry(
        source_id="nsdl_investor_grievance_portal",
        authority="NSDL",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://nsdl.com/investor/investor-grievance"),
        expected_domain="nsdl.com",
        document_type="depository_procedure",
        topic=["depository", "investor_grievance", "grievance_escalation"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="NSDL Official Grievance Redressal Portal and Complaint Handling Structure.",
    ),
    SourceRegistryEntry(
        source_id="nsdl_investor_charter",
        authority="NSDL",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://nsdl.com/investor/investor-charter"),
        expected_domain="nsdl.com",
        document_type="investor_charter",
        topic=["depository", "investor_rights", "investor_grievance"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="NSDL Official Investor Charter for Depositories and Depository Participants.",
    ),

    # --- Zerodha (ORG_ZERODHA) ---
    SourceRegistryEntry(
        source_id="zerodha_charges_schedule",
        organisation_id="ORG_ZERODHA",
        source_class=SourceClass.ORGANISATION_POLICY,
        canonical_url=HttpUrl("https://zerodha.com/charges"),
        expected_domain="zerodha.com",
        document_type="charges_schedule",
        topic=["dp_charges", "brokerage", "amc"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="Zerodha Official List of Charges, Brokerage, and Depository Participant Fees.",
    ),
    SourceRegistryEntry(
        source_id="zerodha_policies_and_procedures",
        organisation_id="ORG_ZERODHA",
        source_class=SourceClass.ORGANISATION_POLICY,
        canonical_url=HttpUrl("https://zerodha.com/policies-and-procedures"),
        expected_domain="zerodha.com",
        document_type="policy",
        topic=["broker_obligations", "trading", "investor_grievance"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="Zerodha Mandatory Client Policies and Operational Procedures.",
    ),

    # --- Groww (ORG_GROWW) ---
    SourceRegistryEntry(
        source_id="groww_pricing_schedule",
        organisation_id="ORG_GROWW",
        source_class=SourceClass.ORGANISATION_POLICY,
        canonical_url=HttpUrl("https://groww.in/pricing"),
        expected_domain="groww.in",
        document_type="charges_schedule",
        topic=["brokerage", "dp_charges"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="Groww Official Brokerage Charges, Demat Charges, and Fee Schedule.",
    ),
    SourceRegistryEntry(
        source_id="groww_grievance_mechanism",
        organisation_id="ORG_GROWW",
        source_class=SourceClass.ORGANISATION_PROCEDURE,
        canonical_url=HttpUrl("https://groww.in/help/customer-grievance-redressal-mechanism"),
        expected_domain="groww.in",
        document_type="grievance_procedure",
        topic=["investor_grievance", "grievance_escalation"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="Groww Customer Grievance Redressal Mechanism and Escalation Hierarchy.",
    ),

    # --- Upstox (ORG_UPSTOX) ---
    SourceRegistryEntry(
        source_id="upstox_brokerage_charges",
        organisation_id="ORG_UPSTOX",
        source_class=SourceClass.ORGANISATION_POLICY,
        canonical_url=HttpUrl("https://upstox.com/brokerage-charges/"),
        expected_domain="upstox.com",
        document_type="charges_schedule",
        topic=["brokerage", "dp_charges"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="Upstox Official Brokerage Charges and Account Fee Structure.",
    ),

    # --- Angel One (ORG_ANGELONE) ---
    SourceRegistryEntry(
        source_id="angelone_exchange_charges",
        organisation_id="ORG_ANGELONE",
        source_class=SourceClass.ORGANISATION_POLICY,
        canonical_url=HttpUrl("https://www.angelone.in/exchange-transaction-charges"),
        expected_domain="angelone.in",
        document_type="charges_schedule",
        topic=["brokerage", "dp_charges"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="Angel One Official Brokerage, Exchange Transaction & Depository Charges.",
    ),
    SourceRegistryEntry(
        source_id="angelone_escalation_matrix",
        organisation_id="ORG_ANGELONE",
        source_class=SourceClass.ORGANISATION_PROCEDURE,
        canonical_url=HttpUrl("https://www.angelone.in/escalation-matrix"),
        expected_domain="angelone.in",
        document_type="escalation_matrix",
        topic=["investor_grievance", "grievance_escalation"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="Angel One Official Investor Redressal and Grievance Escalation Matrix.",
    ),

    # --- ICICI Direct (ORG_ICICIDIRECT) ---
    SourceRegistryEntry(
        source_id="icicidirect_brokerage_plans",
        organisation_id="ORG_ICICIDIRECT",
        source_class=SourceClass.ORGANISATION_POLICY,
        canonical_url=HttpUrl("https://www.icicidirect.com/brokerage"),
        expected_domain="icicidirect.com",
        document_type="charges_schedule",
        topic=["brokerage", "dp_charges"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="ICICI Direct Official Equity Brokerage Plans and Fee Structure.",
    ),
    SourceRegistryEntry(
        source_id="icicidirect_escalation_matrix",
        organisation_id="ORG_ICICIDIRECT",
        source_class=SourceClass.ORGANISATION_PROCEDURE,
        canonical_url=HttpUrl("https://www.icicidirect.com/mailimages/Escalation_Matrix.pdf"),
        expected_domain="icicidirect.com",
        document_type="escalation_matrix",
        topic=["investor_grievance", "grievance_escalation"],
        discovery_method=DiscoveryMethod.EXPLICIT_URL,
        refresh_policy=RefreshPolicy.WEEKLY,
        description="ICICI Direct Official Customer Service and Escalation Matrix PDF.",
    ),
]


class SourceRegistry:
    """In-memory and persistent manager for SANGYAN Official Source Registry."""

    def __init__(self, initial_sources: Sequence[SourceRegistryEntry] | None = None) -> None:
        self._sources: dict[str, SourceRegistryEntry] = {}
        sources_to_load = initial_sources if initial_sources is not None else DEFAULT_OFFICIAL_SOURCES
        for src in sources_to_load:
            self.register_source(src)

    def register_source(self, entry: SourceRegistryEntry) -> None:
        """Register or update an authoritative source."""
        self._sources[entry.source_id] = entry

    def get_source(self, source_id: str) -> SourceRegistryEntry | None:
        """Fetch registered source by unique source_id."""
        return self._sources.get(source_id)

    def list_sources(
        self,
        authority: str | None = None,
        organisation_id: str | None = None,
        source_class: SourceClass | None = None,
        topic: str | None = None,
        active_only: bool = True,
    ) -> list[SourceRegistryEntry]:
        """List registered sources with deterministic filtering."""
        results: list[SourceRegistryEntry] = []
        for src in self._sources.values():
            if active_only and not src.active:
                continue
            if authority and src.authority != authority:
                continue
            if organisation_id and src.organisation_id != organisation_id:
                continue
            if source_class and src.source_class != source_class:
                continue
            if topic and topic not in src.topic:
                continue
            results.append(src)
        return results

    def update_check_record(
        self,
        source_id: str,
        checked_at: datetime,
        content_hash: str | None = None,
        success: bool = True,
    ) -> None:
        """Record check timestamp and content fingerprint for an active source."""
        entry = self._sources.get(source_id)
        if entry:
            entry.last_checked_at = checked_at
            if success:
                entry.last_successful_fetch_at = checked_at
            if content_hash:
                entry.last_content_hash = content_hash
