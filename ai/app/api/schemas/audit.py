"""Audit Trail and Immutable Event History Schemas for SANGYAN Frontend API.

Epistemic foundation:
- Exposes immutable case event stream.
- Supports client query filtering (?after_version=, ?limit=).
- Fully traceable: correlates turns, events, actors, and assessment transitions.
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class AuditEventView(BaseModel):
    """Frontend-safe representation of an immutable case event."""
    event_id: str
    case_id: str
    case_version: int
    event_type: str
    actor: str = "SYSTEM"
    source: str = "web"
    timestamp: datetime
    turn_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    assessment_status: str | None = None
    findings_count: int | None = None


class CaseAuditResponse(BaseModel):
    """Authoritative audit query response."""
    case_id: str
    current_version: int
    total_events: int
    events: list[AuditEventView] = Field(default_factory=list)
