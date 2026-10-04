"""WebSocket Event Envelopes and Serialization for SANGYAN.

Epistemic foundation:
- Adapts canonical CaseEvent stream into deterministic, transport-safe JSON envelopes.
- WebSocket is for event streaming, not independent case mutation.
- The persisted case event stream remains authoritative.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid
from pydantic import BaseModel, Field

from ai.app.case.contracts import CaseEvent, CaseEventType


class WSEventType(str, Enum):
    """Event types streamed over WebSocket."""
    CASE_STATE_CHANGED = "CASE_STATE_CHANGED"
    FACT_EXTRACTED = "FACT_EXTRACTED"
    EVIDENCE_ACCEPTED = "EVIDENCE_ACCEPTED"
    EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
    CLAIM_REGISTERED = "CLAIM_REGISTERED"
    CLAIM_RESOLVED = "CLAIM_RESOLVED"
    RETRIEVAL_EXECUTED = "RETRIEVAL_EXECUTED"
    ASSESSMENT_EXECUTED = "ASSESSMENT_EXECUTED"
    ASSESSMENT_UPDATED = "ASSESSMENT_UPDATED"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    ACTION_INTENT_CREATED = "ACTION_INTENT_CREATED"
    GENERATION_STARTED = "GENERATION_STARTED"
    GENERATION_COMPLETED = "GENERATION_COMPLETED"
    TURN_COMPLETED = "TURN_COMPLETED"
    ERROR = "ERROR"


class WSEventEnvelope(BaseModel):
    """Deterministic event message sent to WebSocket subscribers."""
    event_id: str = Field(default_factory=lambda: f"WSE-{uuid.uuid4().hex[:8].upper()}")
    case_id: str
    turn_id: str | None = None
    version: int
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = Field(default_factory=dict)


def case_event_to_envelope(event: CaseEvent, turn_id: str | None = None) -> WSEventEnvelope:
    """Map internal CaseEvent to transport-safe WebSocket envelope."""
    payload = event.payload or {}
    tid = turn_id or payload.get("turn_id")
    ev_type = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)

    return WSEventEnvelope(
        event_id=event.event_id,
        case_id=event.case_id,
        turn_id=tid,
        version=event.case_version,
        event_type=ev_type,
        timestamp=event.created_at.isoformat() if hasattr(event.created_at, "isoformat") else str(event.created_at),
        payload=payload,
    )
