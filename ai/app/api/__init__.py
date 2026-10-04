"""SANGYAN Transport Layer Package (FastAPI REST and WebSocket).

Epistemic foundation:
- Transport remains thin.
- CaseOrchestrator is the single authoritative execution boundary.
"""

from ai.app.api.app import app, create_app

__all__ = ["app", "create_app"]
