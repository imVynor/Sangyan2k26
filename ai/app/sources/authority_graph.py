"""Source Authority Graph for SANGYAN knowledge domain routing.

Defines machine-readable relationships between regulatory authorities, market infrastructure
institutions (exchanges, depositories), and registered market intermediaries (brokers).

This is a retrieval-routing structure, NOT an unsupported legal ontology.
"""

from enum import Enum
from pydantic import BaseModel, Field


class AuthorityType(str, Enum):
    """Classification of regulatory or market infrastructure entity."""
    APEX_REGULATOR = "APEX_REGULATOR"
    STOCK_EXCHANGE = "STOCK_EXCHANGE"
    DEPOSITORY = "DEPOSITORY"
    CLEARING_CORPORATION = "CLEARING_CORPORATION"
    MARKET_INTERMEDIARY = "MARKET_INTERMEDIARY"


class RegulatedDomain(str, Enum):
    """Functional market domain regulated or operated by an entity."""
    STOCK_BROKING = "STOCK_BROKING"
    DEPOSITORY_SERVICES = "DEPOSITORY_SERVICES"
    EXCHANGE_TRADING = "EXCHANGE_TRADING"
    CLEARING_SETTLEMENT = "CLEARING_SETTLEMENT"
    GRIEVANCE_ODR = "GRIEVANCE_ODR"


class AuthorityNode(BaseModel):
    """Node in the authority retrieval-routing hierarchy."""
    authority_id: str = Field(description="Unique code (e.g. 'SEBI', 'NSE', 'BSE', 'CDSL', 'NSDL').")
    authority_type: AuthorityType
    jurisdiction: str = "India"
    regulates: list[str] = Field(default_factory=list, description="Subordinate entity types or roles regulated.")
    domains: list[RegulatedDomain] = Field(default_factory=list)
    description: str | None = None


# Machine-readable Authority Routing Hierarchy
AUTHORITY_NODES: dict[str, AuthorityNode] = {
    "SEBI": AuthorityNode(
        authority_id="SEBI",
        authority_type=AuthorityType.APEX_REGULATOR,
        regulates=["STOCK_BROKER", "DEPOSITORY", "STOCK_EXCHANGE", "CLEARING_CORPORATION"],
        domains=[
            RegulatedDomain.STOCK_BROKING,
            RegulatedDomain.DEPOSITORY_SERVICES,
            RegulatedDomain.EXCHANGE_TRADING,
            RegulatedDomain.GRIEVANCE_ODR,
        ],
        description="Securities and Exchange Board of India (Statutory Apex Regulator).",
    ),
    "NSE": AuthorityNode(
        authority_id="NSE",
        authority_type=AuthorityType.STOCK_EXCHANGE,
        regulates=["TRADING_MEMBER"],
        domains=[RegulatedDomain.EXCHANGE_TRADING, RegulatedDomain.GRIEVANCE_ODR],
        description="National Stock Exchange of India (Recognised Exchange).",
    ),
    "BSE": AuthorityNode(
        authority_id="BSE",
        authority_type=AuthorityType.STOCK_EXCHANGE,
        regulates=["TRADING_MEMBER"],
        domains=[RegulatedDomain.EXCHANGE_TRADING, RegulatedDomain.GRIEVANCE_ODR],
        description="BSE Limited (Recognised Exchange).",
    ),
    "CDSL": AuthorityNode(
        authority_id="CDSL",
        authority_type=AuthorityType.DEPOSITORY,
        regulates=["DEPOSITORY_PARTICIPANT"],
        domains=[RegulatedDomain.DEPOSITORY_SERVICES, RegulatedDomain.GRIEVANCE_ODR],
        description="Central Depository Services (India) Limited.",
    ),
    "NSDL": AuthorityNode(
        authority_id="NSDL",
        authority_type=AuthorityType.DEPOSITORY,
        regulates=["DEPOSITORY_PARTICIPANT"],
        domains=[RegulatedDomain.DEPOSITORY_SERVICES, RegulatedDomain.GRIEVANCE_ODR],
        description="National Securities Depository Limited.",
    ),
}


class AuthorityGraph:
    """Provides routing paths from case domains to relevant authorities."""

    def __init__(self, nodes: dict[str, AuthorityNode] | None = None) -> None:
        self.nodes = nodes or AUTHORITY_NODES

    def get_apex_regulator(self) -> AuthorityNode:
        """Return primary apex regulator (SEBI)."""
        return self.nodes["SEBI"]

    def get_authorities_for_domain(self, domain: RegulatedDomain) -> list[str]:
        """Return authorities with jurisdiction over a given functional domain."""
        return [node.authority_id for node in self.nodes.values() if domain in node.domains]
