"""Contracts and data models for SANGYAN Case Semantic Normalization and Query Planning.

Epistemic foundation:
- Epistemic origin tracking: USER_ASSERTED, DOCUMENT_ASSERTED, DERIVED, MODEL_INTERPRETATION.
- Strict epistemic boundary: Model interpretations are NEVER converted to user-asserted facts.
- Separation of concerns: CaseSemanticRepresentation is a derived reasoning artifact for
  retrieval and assessment, NOT a duplicate CaseState.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class EpistemicSourceType(str, Enum):
    """Categorical epistemic provenance of semantic fields."""
    USER_ASSERTED = "USER_ASSERTED"
    DOCUMENT_ASSERTED = "DOCUMENT_ASSERTED"
    DERIVED = "DERIVED"
    MODEL_INTERPRETATION = "MODEL_INTERPRETATION"
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"


class QueryType(str, Enum):
    """Functional purpose and strategy of a planned retrieval query."""
    PRIMARY_ISSUE = "PRIMARY_ISSUE"
    CHARGE_OR_TRANSACTION = "CHARGE_OR_TRANSACTION"
    REGULATORY_CONCEPT = "REGULATORY_CONCEPT"
    ORGANISATION_POLICY = "ORGANISATION_POLICY"
    PROCEDURE = "PROCEDURE"
    TEMPORAL = "TEMPORAL"
    CROSS_ORGANISATION = "CROSS_ORGANISATION"


class PlannedQuery(BaseModel):
    """A concrete, structured retrieval query emitted by the query planner."""
    query_id: str
    query_text: str = Field(description="Search text formulated for lexical and dense retrieval.")
    query_type: QueryType = Field(default=QueryType.PRIMARY_ISSUE)
    target_organisation: str | None = Field(default=None, description="e.g. 'ORG_ZERODHA'")
    target_authorities: list[str] = Field(default_factory=list, description="e.g. ['SEBI', 'CDSL']")
    key_terms: list[str] = Field(default_factory=list)
    incident_date: date | None = None
    reference_date: date | None = None
    weight: float = 1.0


class CaseSemanticRepresentation(BaseModel):
    """Normalized semantic interpretation of a grievance for retrieval and reasoning.
    
    Derived from raw user text, documents, and current case state.
    """
    case_id: str = ""
    raw_text: str = ""
    
    # 1. Entity and Intermediary
    organisation: str | None = None
    organisation_id: str | None = None  # e.g. "ORG_ZERODHA"
    relevant_entities: list[str] = Field(default_factory=list)
    portal: str | None = None  # e.g. "SEBI_SCORES", "SMART_ODR"
    authority: str | None = None  # e.g. "SEBI", "CDSL", "NSDL"
    
    # 2. Product and Instrument
    product: str | None = None  # e.g. "MTF", "demat"
    product_type: str | None = None  # e.g. "direct_mutual_fund", "equity_cash"
    instrument: str | None = None  # e.g. "equity_cash", "options", "futures"
    segment: str | None = None  # e.g. "futures", "options", "equity"
    account_type: str | None = None  # e.g. "BSDA", "REGULAR"
    is_bsda: bool | None = None
    
    # 3. Dates and Temporal Context
    incident_date: date | None = None
    incident_date_status: str = "UNRESOLVED"  # "EXACT", "APPROXIMATE", "UNRESOLVED"
    reference_date: date | None = None
    settlement_date: date | None = None
    clearing_date: date | None = None
    elapsed_days: int | None = None
    elapsed_months: int | None = None
    elapsed_hours: int | None = None
    response_days: int | None = None
    
    # 4. Transaction and Action
    transaction_type: str | None = None  # e.g. "equity_delivery_sell", "intraday_equity"
    transaction_subtype: str | None = None
    action: str | None = None  # e.g. "margin_pledge_creation", "share_transfer"
    process: str | None = None  # e.g. "account_opening", "account_closure"
    order_channel: str | None = None  # e.g. "phone_call_and_trade"
    payment_mode: str | None = None  # e.g. "UPI", "netbanking"
    
    # 5. Monetary Components (Strict Decimal arithmetic)
    disputed_amount: Decimal | None = None
    charged_amount: Decimal | None = None
    order_value: Decimal | None = None
    portfolio_value: Decimal | None = None
    turnover: Decimal | None = None
    total_charges: Decimal | None = None
    fee_paid: Decimal | None = None
    currency: str = "INR"
    is_amount_approximate: bool = False
    
    # 6. Issue & Regulatory Concepts
    issue_type: str | None = None  # e.g. "DP_CHARGE", "BROKERAGE_CHARGE"
    issue_subtype: str | None = None
    charge_type: str | None = None  # e.g. "dp_charges", "annual_maintenance_charge"
    charge_description: str | None = None
    regulatory_concepts: list[str] = Field(default_factory=list)
    retrieval_concepts: list[str] = Field(default_factory=list)
    
    # 7. Claims and Unresolved
    user_claims: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    conflicting_claims: list[str] = Field(default_factory=list)
    
    # 8. Epistemic Metadata
    epistemic_origins: dict[str, EpistemicSourceType] = Field(default_factory=dict)
    confidence_metadata: dict[str, Any] = Field(default_factory=dict)
    
    # 9. Planned Retrieval Queries
    planned_queries: list[PlannedQuery] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
