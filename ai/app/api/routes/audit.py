"""Case Audit Trail and Event Query REST Endpoints for SANGYAN.

Epistemic foundation:
- Exposes immutable case event stream.
- Supports ?after_version= and ?limit= filtering for client polling or synchronization.
- Strictly read-only; never mutates case state.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Query

from ai.app.api.dependencies import get_orchestrator, verify_case_access
from ai.app.api.errors import CaseNotFoundError
from ai.app.api.schemas.audit import AuditEventView, CaseAuditResponse
from ai.app.orchestration.audit import AuditReconstructor
from ai.app.orchestration.orchestrator import CaseOrchestrator

audit_router = APIRouter(prefix="/cases/{case_id}/audit", tags=["Audit"])


@audit_router.get(
    "",
    response_model=CaseAuditResponse,
    summary="Retrieve immutable event timeline and assessment audit trail",
    dependencies=[Depends(verify_case_access)],
)
async def get_case_audit_trail(
    case_id: str,
    orchestrator: Annotated[CaseOrchestrator, Depends(get_orchestrator)],
    after_version: int | None = Query(default=None, description="Fetch events occurring strictly after this version"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum events to return"),
) -> CaseAuditResponse:
    """Query chronological case events with correlated assessment snapshots."""
    case_state = await orchestrator.repository.get_case(case_id)
    if not case_state:
        raise CaseNotFoundError(case_id=case_id)

    raw_timeline = AuditReconstructor.reconstruct_timeline(case_state)

    filtered = raw_timeline
    if after_version is not None:
        filtered = [item for item in filtered if item.get("case_version", 0) > after_version]

    events_view: list[AuditEventView] = []
    for item in filtered[:limit]:
        events_view.append(AuditEventView(
            event_id=item["event_id"],
            case_id=case_id,
            case_version=item["case_version"],
            event_type=item["event_type"],
            actor=item.get("actor", "SYSTEM"),
            source=item.get("source", "web"),
            timestamp=item["timestamp"],
            turn_id=item.get("payload", {}).get("turn_id"),
            payload=item.get("payload", {}),
            assessment_status=item.get("assessment_status"),
            findings_count=item.get("findings_count"),
        ))

    return CaseAuditResponse(
        case_id=case_id,
        current_version=case_state.version,
        total_events=len(case_state.interaction_history),
        events=events_view,
    )
