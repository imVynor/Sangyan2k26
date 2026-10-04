"""Domain Issue and Concept Taxonomy for SANGYAN Grievance Reasoning.

Epistemic foundation:
- Derived directly from actual Indian capital market regulations (SEBI, CDSL, NSDL)
  and broker fee schedules (Zerodha, Angel One, Groww, Upstox, ICICI Direct).
- Unrecognized or ambiguous grievance topics default to UNKNOWN_CONCEPT,
  avoiding premature or incorrect categorical commitment.
"""

from enum import Enum


class IssueDomainConcept(str, Enum):
    """Controlled vocabulary of primary grievance and regulatory issues."""
    DP_CHARGE = "DP_CHARGE"
    BROKERAGE_CHARGE = "BROKERAGE_CHARGE"
    ACCOUNT_MAINTENANCE_CHARGE = "ACCOUNT_MAINTENANCE_CHARGE"
    TRANSACTION_CHARGE = "TRANSACTION_CHARGE"
    MARGIN_PLEDGE = "MARGIN_PLEDGE"
    ACCOUNT_OPENING = "ACCOUNT_OPENING"
    ACCOUNT_CLOSURE = "ACCOUNT_CLOSURE"
    DEMAT_STATEMENT = "DEMAT_STATEMENT"
    SCORES_COMPLAINT = "SCORES_COMPLAINT"
    DEPOSITORY_ESCALATION = "DEPOSITORY_ESCALATION"
    SETTLEMENT_CYCLE = "SETTLEMENT_CYCLE"
    DDPI_POA = "DDPI_POA"
    STT_STAMP_DUTY = "STT_STAMP_DUTY"
    IPO_APPLICATION = "IPO_APPLICATION"
    DIRECT_PAYOUT = "DIRECT_PAYOUT"
    KYC_PAN = "KYC_PAN"
    CONTRACT_NOTE = "CONTRACT_NOTE"
    UNAUTHORIZED_TRANSACTION = "UNAUTHORIZED_TRANSACTION"
    BSDA_ELIGIBILITY = "BSDA_ELIGIBILITY"
    AUCTION_SHORTAGE = "AUCTION_SHORTAGE"
    DIVIDEND_TDS = "DIVIDEND_TDS"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    COLLATERAL_REPORTING = "COLLATERAL_REPORTING"
    CALL_AND_TRADE = "CALL_AND_TRADE"
    MUTUAL_FUND = "MUTUAL_FUND"
    CRYPTOCURRENCY_UNREGULATED = "CRYPTOCURRENCY_UNREGULATED"
    UNREGISTERED_ADVISORY = "UNREGISTERED_ADVISORY"
    UNKNOWN_CONCEPT = "UNKNOWN_CONCEPT"


class RegulatoryAuthorityConcept(str, Enum):
    """Authoritative apex bodies and market infrastructure institutions."""
    SEBI = "SEBI"
    CDSL = "CDSL"
    NSDL = "NSDL"
    NSE = "NSE"
    BSE = "BSE"
    UNKNOWN = "UNKNOWN"
