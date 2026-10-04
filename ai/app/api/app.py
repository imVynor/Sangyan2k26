"""FastAPI Application Factory and Transport Middleware for SANGYAN.

Epistemic foundation:
- Transport must remain thin. The CaseOrchestrator remains the single authoritative execution boundary.
- Enforces request correlation via X-Request-ID.
- Versioned endpoints mounted at /api/v1.
- Global deterministic exception handling and security boundaries.
"""

from datetime import datetime, timezone
from typing import Any, Callable
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from ai.app.api.errors import register_error_handlers
from ai.app.api.routes.audit import audit_router
from ai.app.api.routes.cases import cases_router
from ai.app.api.routes.turns import turns_router
from ai.app.api.websocket.handlers import ws_router
from ai.app.api.websocket.manager import ConnectionManager
from ai.app.config.settings import settings
from ai.app.generation.generator import AuditableResponseGenerator
from ai.app.models.ollama import OllamaProvider
from ai.app.orchestration.orchestrator import CaseOrchestrator


def create_app(
    orchestrator: CaseOrchestrator | None = None,
    ws_manager: ConnectionManager | None = None,
) -> FastAPI:
    """Instantiate and configure the SANGYAN FastAPI application."""
    app = FastAPI(
        title="SANGYAN Epistemic Grievance API",
        description="Authoritative, auditable API for Indian securities and brokerage grievance reasoning.",
        version="1.0.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
    )

    # Initialize and attach singleton services to app.state
    if orchestrator is not None:
        app.state.orchestrator = orchestrator
    else:
        repository = None
        if settings.database_url:
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

            from ai.app.case.repository import PostgresCaseRepository
            from ai.app.db.session import get_async_engine

            repository = PostgresCaseRepository(
                async_sessionmaker(
                    bind=get_async_engine(),
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=False,
                )
            )
        response_provider = OllamaProvider(
            model_name=settings.response_model,
            timeout=settings.response_generation_timeout,
        )
        app.state.orchestrator = CaseOrchestrator(
            repository=repository,
            generator=AuditableResponseGenerator(llm_provider=response_provider),
        )
    app.state.ws_manager = ws_manager if ws_manager is not None else ConnectionManager()

    # CORS configuration for frontend clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Correlation ID Middleware
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next: Any) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"REQ-{uuid.uuid4().hex[:8].upper()}"
        request.state.request_id = req_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    # Register error handlers
    register_error_handlers(app)

    # Health check endpoints
    @app.get("/health", tags=["Health"])
    @app.get("/api/v1/health", tags=["Health"])
    async def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": "SANGYAN API",
            "version": "1.0.0",
            "knowledge_snapshot_id": app.state.orchestrator.knowledge_snapshot_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Mount API v1 Routers
    api_v1_prefix = "/api/v1"
    app.include_router(cases_router, prefix=api_v1_prefix)
    app.include_router(turns_router, prefix=api_v1_prefix)
    app.include_router(audit_router, prefix=api_v1_prefix)
    app.include_router(ws_router, prefix=api_v1_prefix)

    return app


# Default ASGI application instance for uvicorn
app = create_app()
