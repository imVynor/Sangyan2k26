"""Core schemas for SANGYAN model abstraction and structured case understanding.

Epistemic foundation:
- FACT: directly stated or supported by external verified source.
- CLAIM: something the user alleges or concludes (must not become fact without verification).
- HYPOTHESIS: a possible explanation not yet established.
- UNKNOWN: information necessary for reasoning but currently unavailable.
"""

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class Role(str, Enum):
    """Supported message roles."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """Represents a chat message in a provider-agnostic manner."""
    role: Literal["system", "user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    """Standardized request envelope for LLM generation."""
    messages: list[Message]
    temperature: float = 0.0
    max_tokens: int | None = None
    response_schema_name: str | None = None


class LLMResponse(BaseModel):
    """Standardized response envelope from an LLM provider."""
    content: str
    model: str
    provider: str
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    raw_response: dict[str, Any] | None = None


# =====================================================================
# Epistemic Schemas for SANGYAN Case Understanding
# =====================================================================

class EpistemicStatus(str, Enum):
    """Status indicating the epistemic validity of a fact or claim.
    
    Foundational rule: Never silently convert CLAIM or HYPOTHESIS into FACT.
    """
    USER_ASSERTED = "USER_ASSERTED"
    MODEL_INFERRED = "MODEL_INFERRED"
    SOURCE_SUPPORTED = "SOURCE_SUPPORTED"
    CONFIRMED = "CONFIRMED"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class Entity(BaseModel):
    """Named entity identified in the case narrative (e.g. broker, depository, investor)."""
    name: str = Field(description="Name or generic descriptor of the entity (e.g., 'Zerodha', 'broker')")
    category: str = Field(description="Type of entity: e.g. broker, exchange, depository, bank, regulator, investor")
    details: str | None = Field(default=None, description="Additional context or role in the case")


class Fact(BaseModel):
    """Something directly stated by the user or supported by verifiable records."""
    statement: str = Field(description="The factual statement")
    status: EpistemicStatus = Field(
        default=EpistemicStatus.USER_ASSERTED,
        description="Epistemic status of the fact"
    )
    source: str | None = Field(default=None, description="Attribution source (e.g., 'user_statement', 'ledger')")


class Claim(BaseModel):
    """Something the user alleges, infers, or concludes (e.g. 'This is illegal', 'Broker cheated me')."""
    statement: str = Field(description="The user claim or allegation")
    status: EpistemicStatus = Field(
        default=EpistemicStatus.USER_ASSERTED,
        description="Epistemic status of the claim"
    )
    basis: str | None = Field(default=None, description="The reasoning or perceived basis for the claim")


class Unknown(BaseModel):
    """Information necessary for regulatory/operational reasoning that is currently missing."""
    item: str = Field(description="Description of what piece of information is missing")
    importance: str | None = Field(default="critical", description="Level of importance: critical, high, moderate")
    reason: str | None = Field(default=None, description="Why this missing information is needed")


class Hypothesis(BaseModel):
    """A plausible explanation for the issue that has NOT yet been established as fact."""
    description: str = Field(description="Plausible explanation of what might have occurred")
    likelihood: str | None = Field(default=None, description="Tentative assessment: plausible, possible, unlikely")
    investigation_needed: str | None = Field(default=None, description="What would verify or refute this hypothesis")


class CaseUnderstanding(BaseModel):
    """Structured understanding of an investor grievance case narrative.
    
    This structured state is owned by the system and passed down the pipeline,
    ensuring the LLM does not hallucinate regulatory conclusions or convert
    unverified claims into accepted facts.
    """
    intent: str = Field(
        description="Identified user intent, e.g. 'report_unauthorized_debit', 'seek_grievance_redressal'"
    )
    entities: list[Entity] = Field(
        default_factory=list,
        description="Entities involved in the transaction or dispute"
    )
    facts: list[Fact] = Field(
        default_factory=list,
        description="Facts directly asserted by the user or records"
    )
    claims: list[Claim] = Field(
        default_factory=list,
        description="Allegations, interpretations, or conclusions made by the user"
    )
    unknowns: list[Unknown] = Field(
        default_factory=list,
        description="Missing facts or details required to evaluate regulations"
    )
    hypotheses: list[Hypothesis] = Field(
        default_factory=list,
        description="Plausible explanations (e.g. annual maintenance charge, DP charges, margin shortfall)"
    )
    next_question: str | None = Field(
        default=None,
        description="Suggested targeted clarifying question to ask the user"
    )
