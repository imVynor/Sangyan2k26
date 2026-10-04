"""Knowledge Domain Routing for cross-organisation and multi-authority retrieval.

Translates case issues and organisation context into targeted regulatory authorities,
market infrastructure institutions, and intermediary documentation.
"""

from enum import Enum
from pydantic import BaseModel, Field

from ai.app.sources.authority_graph import AuthorityGraph, RegulatedDomain


class KnowledgeDomain(str, Enum):
    """Categorical domain topics for routing and provision filtering."""
    BROKER = "BROKER"
    DEPOSITORY = "DEPOSITORY"
    STOCK_EXCHANGE = "STOCK_EXCHANGE"
    CLEARING_CORPORATION = "CLEARING_CORPORATION"
    INVESTOR_GRIEVANCE = "INVESTOR_GRIEVANCE"
    TRADING = "TRADING"
    DEMATERIALISATION = "DEMATERIALISATION"
    DEMAT_TRANSFER = "DEMAT_TRANSFER"
    DP_CHARGES = "DP_CHARGES"
    BROKERAGE = "BROKERAGE"
    AMC = "AMC"
    PLEDGE = "PLEDGE"
    UNPLEDGE = "UNPLEDGE"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    ACCOUNT_CLOSURE = "ACCOUNT_CLOSURE"
    KYC = "KYC"
    FUNDS = "FUNDS"
    SECURITIES = "SECURITIES"
    GRIEVANCE_ESCALATION = "GRIEVANCE_ESCALATION"
    ODR = "ODR"
    SCORES = "SCORES"


class RoutingTarget(BaseModel):
    """Explicitly routed query target containing candidate authorities and organisations."""
    authorities: list[str] = Field(description="List of regulatory/infrastructure authorities to query (e.g. ['SEBI', 'CDSL']).")
    organisation_id: str | None = Field(default=None, description="Market intermediary to query if relevant.")
    activated_domains: list[KnowledgeDomain] = Field(default_factory=list)
    include_exchanges: bool = False
    include_depositories: bool = False


class DomainRouter:
    """Routes case issues to authoritative bodies without hallucinations."""

    def __init__(self, authority_graph: AuthorityGraph | None = None) -> None:
        self.graph = authority_graph or AuthorityGraph()

    def route_case(
        self,
        domains: list[KnowledgeDomain],
        organisation_id: str | None = None,
    ) -> RoutingTarget:
        """Deterministically determine relevant authorities and source targets for given case domains."""
        activated_set = set(domains)
        authorities: set[str] = {"SEBI"}  # Apex regulator always applies to securities disputes

        # Expand domain dependencies
        if KnowledgeDomain.DP_CHARGES in activated_set:
            activated_set.add(KnowledgeDomain.DEPOSITORY)
            activated_set.add(KnowledgeDomain.BROKER)
            activated_set.add(KnowledgeDomain.INVESTOR_GRIEVANCE)

        if KnowledgeDomain.DEMAT_TRANSFER in activated_set or KnowledgeDomain.DEMATERIALISATION in activated_set:
            activated_set.add(KnowledgeDomain.DEPOSITORY)

        if KnowledgeDomain.TRADING in activated_set:
            activated_set.add(KnowledgeDomain.STOCK_EXCHANGE)
            activated_set.add(KnowledgeDomain.BROKER)

        include_depositories = KnowledgeDomain.DEPOSITORY in activated_set or KnowledgeDomain.DP_CHARGES in activated_set
        include_exchanges = KnowledgeDomain.STOCK_EXCHANGE in activated_set or KnowledgeDomain.TRADING in activated_set

        if include_depositories:
            authorities.add("CDSL")
            authorities.add("NSDL")

        if include_exchanges:
            authorities.add("NSE")
            authorities.add("BSE")

        # Deterministic sort order: Apex regulator first, then infrastructure
        ordered_auths: list[str] = []
        if "SEBI" in authorities:
            ordered_auths.append("SEBI")
        for a in sorted(list(authorities - {"SEBI"})):
            ordered_auths.append(a)

        return RoutingTarget(
            authorities=ordered_auths,
            organisation_id=organisation_id,
            activated_domains=sorted(list(activated_set), key=lambda x: x.value),
            include_exchanges=include_exchanges,
            include_depositories=include_depositories,
        )
