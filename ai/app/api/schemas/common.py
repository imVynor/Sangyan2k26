"""Common Schemas, Error Envelopes, and Value Enums for SANGYAN Transport Layer.

Epistemic foundation:
- Stable transport contracts shielding frontend from internal schema evolution.
- Preserves epistemic distinctions (source class, claim resolution status).
- Standardized error structures with correlation IDs.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ClaimSourceClassView(str, Enum):
    """Categorization of evidence origin for frontend presentation."""
    USER_ASSERTED = "USER_ASSERTED"
    DOCUMENT_ASSERTED = "DOCUMENT_ASSERTED"
    DERIVED = "DERIVED"
    MODEL_INTERPRETATION = "MODEL_INTERPRETATION"


class ClaimStatusView(str, Enum):
    """Epistemic status of an empirical claim for frontend presentation."""
    UNRESOLVED = "UNRESOLVED"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    RESOLVED_BY_POLICY = "RESOLVED_BY_POLICY"
    RESOLVED_BY_ADDITIONAL_EVIDENCE = "RESOLVED_BY_ADDITIONAL_EVIDENCE"


class ErrorDetail(BaseModel):
    """Structured error explanation."""
    code: str = Field(description="Machine-readable error identifier")
    message: str = Field(description="Human-readable explanation")
    details: dict[str, Any] = Field(default_factory=dict, description="Contextual debugging details")
    case_id: str | None = None
    turn_id: str | None = None
    current_version: int | None = None
    is_retryable: bool = False


class APIErrorResponse(BaseModel):
    """Standardized API error envelope."""
    error: ErrorDetail
    request_id: str = Field(description="Correlation identifier for tracing")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class APIResponseEnvelope(BaseModel, Generic[T]):
    """Standardized successful response wrapper."""
    data: T
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
