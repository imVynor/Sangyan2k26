"""Case Lifecycle REST Endpoints for SANGYAN.

Epistemic foundation:
- Transport remains thin; delegates all case mutations strictly to CaseOrchestrator.
- POST /cases bootstraps a case and processes Turn 1 atomically.
- GET /cases/{case_id} returns authoritative, frontend-safe case projection.
"""

import uuid
from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, Header, Request, status

from ai.app.api.dependencies import (
    CurrentPrincipal,
    get_current_principal,
    get_orchestrator,
    verify_case_access,
)
from ai.app.api.errors import CaseNotFoundError
from ai.app.api.schemas.cases import CaseView, map_case_state_to_view
from ai.app.api.schemas.turns import (
    CreateCaseRequest,
    CreateCaseResponse,
    map_turn_result_to_view,
)
from ai.app.api.websocket.manager import ConnectionManager
from ai.app.case.contracts import CaseEventType
from ai.app.orchestration.contracts import OrchestrationInputEvent
from ai.app.orchestration.orchestrator import CaseOrchestrator

cases_router = APIRouter(prefix="/cases", tags=["Cases"])


def _get_ws_manager(request: Request) -> ConnectionManager:
    if not hasattr(request.app.state, "ws_manager") or request.app.state.ws_manager is None:
        request.app.state.ws_manager = ConnectionManager()
    return request.app.state.ws_manager


@cases_router.post(
    "",
    response_model=CreateCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new grievance case and execute Turn 1",
)
async def create_case(
    payload: CreateCaseRequest,
    request: Request,
    orchestrator: Annotated[CaseOrchestrator, Depends(get_orchestrator)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CreateCaseResponse:
    """Initialize a case and evaluate the initial citizen complaint."""
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"

    input_event = OrchestrationInputEvent(
        event_type=CaseEventType.USER_MESSAGE_RECEIVED,
        complaint_text=payload.initial_message,
        user_message=payload.initial_message,
        language=payload.language,
        actor=principal.principal_id,
        source="api/v1/cases",
        metadata=payload.metadata,
        reference_date=date.today(),
    )

    turn_result = await orchestrator.process_turn(
        case_id=case_id,
        input_event=input_event,
        expected_version=None,
        idempotency_key=idempotency_key,
    )

    # Broadcast turn events to connected listeners
    ws_mgr = _get_ws_manager(request)
    await ws_mgr.broadcast_turn_events(case_id, turn_result)

    return CreateCaseResponse(
        case_id=case_id,
        version=turn_result.new_version,
        status=turn_result.new_status.value if hasattr(turn_result.new_status, "value") else str(turn_result.new_status),
        turn_id=turn_result.turn_id,
        response=map_turn_result_to_view(turn_result),
    )


@cases_router.get(
    "/{case_id}",
    response_model=CaseView,
    summary="Retrieve current authoritative case projection",
    dependencies=[Depends(verify_case_access)],
)
async def get_case(
    case_id: str,
    orchestrator: Annotated[CaseOrchestrator, Depends(get_orchestrator)],
) -> CaseView:
    """Fetch structured frontend-safe view of the current case state."""
    case_state = await orchestrator.repository.get_case(case_id)
    if not case_state:
        raise CaseNotFoundError(case_id=case_id)

    return map_case_state_to_view(case_state)
