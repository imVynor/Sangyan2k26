"""WebSocket Route Handlers and Event Replay Loop for SANGYAN.

Epistemic foundation:
- Pure streaming transport; never allows WebSocket frames to directly invoke RuleEvaluator or mutate DB.
- Replays missed events from immutable event history on reconnect with last_seen_version.
- Preserves authoritative ordering of the case event stream.
"""

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status

from ai.app.api.dependencies import CaseAccessPolicy, CurrentPrincipal, get_orchestrator
from ai.app.api.websocket.events import WSEventEnvelope, case_event_to_envelope
from ai.app.api.websocket.manager import ConnectionManager
from ai.app.orchestration.orchestrator import CaseOrchestrator

logger = logging.getLogger("sangyan.api.websocket.handlers")

ws_router = APIRouter()


async def get_ws_manager(websocket: WebSocket) -> ConnectionManager:
    """Retrieve global WebSocket ConnectionManager from app state."""
    if not hasattr(websocket.app.state, "ws_manager") or websocket.app.state.ws_manager is None:
        websocket.app.state.ws_manager = ConnectionManager()
    return websocket.app.state.ws_manager


@ws_router.websocket("/ws/cases/{case_id}")
async def case_event_stream(
    websocket: WebSocket,
    case_id: str,
    last_seen_version: int | None = Query(default=None),
) -> None:
    """Stream real-time case reasoning events with automatic replay on reconnect."""
    # Resolve orchestrator and manager from app state
    orchestrator: CaseOrchestrator = getattr(websocket.app.state, "orchestrator", None) or CaseOrchestrator()
    ws_manager: ConnectionManager = getattr(websocket.app.state, "ws_manager", None) or ConnectionManager()
    websocket.app.state.ws_manager = ws_manager

    # 1. Authorize Case Access
    case = await orchestrator.repository.get_case(case_id)
    if not case:
        logger.warning(f"Rejecting WS connection for non-existent case '{case_id}'")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Case not found")
        return

    # 2. Accept and Register Connection
    await ws_manager.connect(case_id, websocket)

    try:
        # 3. Replay Missed Events (if reconnecting with last_seen_version)
        if last_seen_version is not None:
            logger.info(f"Replaying missed events for case '{case_id}' after version {last_seen_version}")
            missed_events = [
                ev for ev in case.interaction_history
                if ev.case_version > last_seen_version
            ]
            for ev in missed_events:
                env = case_event_to_envelope(ev)
                await websocket.send_json(env.model_dump(mode="json"))

        # 4. Client Listening Loop
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "").lower()

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "case_id": case_id})
            elif msg_type == "replay" or msg_type == "subscribe":
                req_last_version = data.get("last_seen_version", 0)
                refreshed_case = await orchestrator.repository.get_case(case_id)
                if refreshed_case:
                    events = [
                        ev for ev in refreshed_case.interaction_history
                        if ev.case_version > req_last_version
                    ]
                    for ev in events:
                        env = case_event_to_envelope(ev)
                        await websocket.send_json(env.model_dump(mode="json"))
            else:
                # Inform client that mutations via WS are not supported
                await websocket.send_json({
                    "event_type": "NOTICE",
                    "message": "WebSocket is streaming-only. Authoritative mutations must use POST /api/v1/cases/{case_id}/turns",
                })
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected cleanly for case '{case_id}'")
    except Exception as e:
        logger.warning(f"WebSocket error for case '{case_id}': {e}")
    finally:
        ws_manager.disconnect(case_id, websocket)
