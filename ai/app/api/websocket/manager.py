"""WebSocket Connection Manager for SANGYAN Real-Time Streaming.

Epistemic foundation:
- Coordinates active client connections partitioned by case_id.
- Broadcasts deterministic turn events without altering the authoritative event store.
- Supports replay of missed events on connection re-establishment.
"""

from collections import defaultdict
import logging
from typing import Any
from fastapi import WebSocket

from ai.app.api.websocket.events import WSEventEnvelope, case_event_to_envelope
from ai.app.orchestration.contracts import CaseTurnResult

logger = logging.getLogger("sangyan.api.websocket.manager")


class ConnectionManager:
    """Manages active WebSockets and distributes case lifecycle events."""

    def __init__(self) -> None:
        # Map case_id -> set of active WebSockets
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, case_id: str, websocket: WebSocket) -> None:
        """Accept and register a client socket for a given case."""
        await websocket.accept()
        self._connections[case_id].add(websocket)
        logger.info(f"WebSocket client connected to case '{case_id}' (total: {len(self._connections[case_id])})")

    def disconnect(self, case_id: str, websocket: WebSocket) -> None:
        """Unregister a client socket."""
        if case_id in self._connections:
            self._connections[case_id].discard(websocket)
            if not self._connections[case_id]:
                del self._connections[case_id]
        logger.info(f"WebSocket client disconnected from case '{case_id}'")

    async def broadcast_envelope(self, case_id: str, envelope: WSEventEnvelope) -> None:
        """Send an envelope to all connected clients for a case."""
        sockets = list(self._connections.get(case_id, set()))
        if not sockets:
            return

        payload_json = envelope.model_dump(mode="json")
        for ws in sockets:
            try:
                await ws.send_json(payload_json)
            except Exception as e:
                logger.warning(f"Failed to send WS message to client on case '{case_id}': {e}")

    async def broadcast_turn_events(self, case_id: str, turn_result: CaseTurnResult) -> None:
        """Convert and broadcast all events generated during a turn."""
        for evt in turn_result.events_created:
            envelope = case_event_to_envelope(evt, turn_id=turn_result.turn_id)
            await self.broadcast_envelope(case_id, envelope)

    def get_active_connection_count(self, case_id: str) -> int:
        """Return the number of active sockets for a case."""
        return len(self._connections.get(case_id, set()))
