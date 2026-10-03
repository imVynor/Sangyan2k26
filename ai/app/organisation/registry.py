"""Official Organisation Registry for SANGYAN.

Strictly manages authorized market intermediaries and their pinned domains:
- Zerodha
- Groww
- Upstox
- Angel One
- ICICI Direct
"""

from typing import Sequence
from ai.app.organisation.models import OrganisationDiscoveryPage, OrganisationEntry

INITIAL_ORGANISATIONS: list[OrganisationEntry] = [
    OrganisationEntry(
        organisation_id="ORG_ZERODHA",
        canonical_name="Zerodha Broking Limited",
        official_domains=["zerodha.com", "support.zerodha.com"],
        active=True,
        supported_topics=["dp_charges", "brokerage", "investor_grievance", "trading", "account_closure"],
        discovery_pages=[
            OrganisationDiscoveryPage(
                page_type="charges",
                url="https://zerodha.com/charges",
                description="Official Zerodha Brokerage and DP Charge Schedule",
            ),
            OrganisationDiscoveryPage(
                page_type="policies_and_procedures",
                url="https://zerodha.com/policies-and-procedures",
                description="Zerodha Mandatory Client Policies and Operational Procedures",
            ),
        ],
    ),
    OrganisationEntry(
        organisation_id="ORG_GROWW",
        canonical_name="Groww Invest Tech Pvt. Ltd.",
        official_domains=["groww.in"],
        active=True,
        supported_topics=["dp_charges", "brokerage", "investor_grievance", "trading", "mutual_funds"],
        discovery_pages=[
            OrganisationDiscoveryPage(
                page_type="charges",
                url="https://groww.in/pricing",
                description="Groww Pricing and Demat Fee Schedule",
            ),
            OrganisationDiscoveryPage(
                page_type="grievance_mechanism",
                url="https://groww.in/help/customer-grievance-redressal-mechanism",
                description="Groww Grievance Escalation Procedure",
            ),
        ],
    ),
    OrganisationEntry(
        organisation_id="ORG_UPSTOX",
        canonical_name="RKSV Securities India Pvt. Ltd. (Upstox)",
        official_domains=["upstox.com", "help.upstox.com"],
        active=True,
        supported_topics=["dp_charges", "brokerage", "investor_grievance", "trading"],
        discovery_pages=[
            OrganisationDiscoveryPage(
                page_type="charges",
                url="https://upstox.com/brokerage-charges/",
                description="Upstox Brokerage Charges and Account Fee Structure",
            ),
        ],
    ),
    OrganisationEntry(
        organisation_id="ORG_ANGELONE",
        canonical_name="Angel One Limited",
        official_domains=["angelone.in"],
        active=True,
        supported_topics=["dp_charges", "brokerage", "investor_grievance", "trading", "margin_trading"],
        discovery_pages=[
            OrganisationDiscoveryPage(
                page_type="charges",
                url="https://www.angelone.in/exchange-transaction-charges",
                description="Angel One Official Brokerage, Exchange Transaction & Depository Charges",
            ),
            OrganisationDiscoveryPage(
                page_type="escalation_matrix",
                url="https://www.angelone.in/escalation-matrix",
                description="Angel One Grievance Escalation Mechanism",
            ),
        ],
    ),
    OrganisationEntry(
        organisation_id="ORG_ICICIDIRECT",
        canonical_name="ICICI Securities Limited (ICICI Direct)",
        official_domains=["icicidirect.com"],
        active=True,
        supported_topics=["dp_charges", "brokerage", "investor_grievance", "trading", "demat_transfer"],
        discovery_pages=[
            OrganisationDiscoveryPage(
                page_type="charges",
                url="https://www.icicidirect.com/brokerage",
                description="ICICI Direct Official Equity Brokerage Plans and Fee Structure",
            ),
            OrganisationDiscoveryPage(
                page_type="escalation_matrix",
                url="https://www.icicidirect.com/mailimages/Escalation_Matrix.pdf",
                description="ICICI Direct Official Customer Service and Escalation Matrix PDF",
            ),
        ],
    ),
]


class OrganisationRegistry:
    """Registry maintaining authoritative profiles of regulated intermediaries."""

    def __init__(self, initial_orgs: Sequence[OrganisationEntry] | None = None) -> None:
        self._orgs: dict[str, OrganisationEntry] = {}
        items = initial_orgs if initial_orgs is not None else INITIAL_ORGANISATIONS
        for org in items:
            self.register_organisation(org)

    def register_organisation(self, entry: OrganisationEntry) -> None:
        """Register or update an organisation profile."""
        self._orgs[entry.organisation_id] = entry

    def get_organisation(self, organisation_id: str) -> OrganisationEntry | None:
        """Fetch organisation by identifier."""
        return self._orgs.get(organisation_id)

    def list_organisations(self, active_only: bool = True) -> list[OrganisationEntry]:
        """List registered organisations."""
        if active_only:
            return [o for o in self._orgs.values() if o.active]
        return list(self._orgs.values())

    def validate_domain_for_org(self, organisation_id: str, domain: str) -> bool:
        """Verify if a domain is an authorized official domain for the given organisation."""
        org = self.get_organisation(organisation_id)
        if not org or not org.active:
            return False
        return org.is_official_domain(domain)
