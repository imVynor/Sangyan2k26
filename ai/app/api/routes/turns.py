"""Turn Execution and Evidence Upload REST Endpoints for SANGYAN.

Epistemic foundation:
- Pure transport boundary; routes all conversational turns and evidence uploads through CaseOrchestrator.
- Enforces strict file validation (MIME types, size limits) before document ingestion.
- Passes Idempotency-Key and expected_version directly to CaseOrchestrator for concurrency control.
"""

from datetime import date
from typing import Annotated
import uuid
from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile, status

from ai.app.api.dependencies import (
    CurrentPrincipal,
    get_current_principal,
    get_orchestrator,
    verify_case_access,
)
from ai.app.api.errors import DocumentTooLargeError, UnsupportedMediaTypeError
from ai.app.api.schemas.turns import (
    CaseTurnResultView,
    SubmitTurnRequest,
    map_turn_result_to_view,
)
from ai.app.api.websocket.manager import ConnectionManager
from ai.app.case.contracts import CaseEventType
from ai.app.extraction.document_extractor import DocumentExtractionPayload
from ai.app.orchestration.contracts import OrchestrationInputEvent
from ai.app.orchestration.orchestrator import CaseOrchestrator

turns_router = APIRouter(prefix="/cases/{case_id}", tags=["Turns"])

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "text/plain",
    "text/csv",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _get_ws_manager(request: Request) -> ConnectionManager:
    if not hasattr(request.app.state, "ws_manager") or request.app.state.ws_manager is None:
        request.app.state.ws_manager = ConnectionManager()
    return request.app.state.ws_manager


@turns_router.post(
    "/turns",
    response_model=CaseTurnResultView,
    summary="Submit a conversational response, clarification, or decline",
    dependencies=[Depends(verify_case_access)],
)
async def submit_turn(
    case_id: str,
    payload: SubmitTurnRequest,
    request: Request,
    orchestrator: Annotated[CaseOrchestrator, Depends(get_orchestrator)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CaseTurnResultView:
    """Submit a citizen dialogue turn and advance the epistemic case state."""
    effective_idempotency_key = idempotency_key_header or payload.idempotency_key

    # Epistemic event classification
    if payload.declined_field:
        evt_type = CaseEventType.USER_DECLINED_EVIDENCE
    else:
        evt_type = CaseEventType.USER_MESSAGE_RECEIVED

    input_event = OrchestrationInputEvent(
        event_type=evt_type,
        user_message=payload.message,
        declined_field=payload.declined_field,
        language=payload.language,
        actor=principal.principal_id,
        source="api/v1/turns",
        metadata=payload.metadata,
        reference_date=date.today(),
    )

    turn_result = await orchestrator.process_turn(
        case_id=case_id,
        input_event=input_event,
        expected_version=payload.expected_version,
        idempotency_key=effective_idempotency_key,
    )

    # Broadcast turn events to connected WebSocket clients
    ws_mgr = _get_ws_manager(request)
    await ws_mgr.broadcast_turn_events(case_id, turn_result)

    return map_turn_result_to_view(turn_result)


@turns_router.post(
    "/evidence",
    response_model=CaseTurnResultView,
    summary="Upload documentary evidence (Contract note, statement, screenshot)",
    dependencies=[Depends(verify_case_access)],
)
async def upload_evidence(
    case_id: str,
    request: Request,
    orchestrator: Annotated[CaseOrchestrator, Depends(get_orchestrator)],
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    file: UploadFile = File(...),
    expected_version: Annotated[int | None, Form()] = None,
    description: Annotated[str, Form()] = "",
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CaseTurnResultView:
    """Upload and integrate documentary evidence into the case."""
    mime = file.content_type or "application/octet-stream"
    if mime not in SUPPORTED_MIME_TYPES:
        raise UnsupportedMediaTypeError(mime_type=mime, supported=sorted(list(SUPPORTED_MIME_TYPES)))

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentTooLargeError(size_bytes=len(content), max_bytes=MAX_UPLOAD_BYTES)

    text_content = ""
    if mime in ("text/plain", "text/csv"):
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            text_content = content.decode("latin-1", errors="ignore")

    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    extractor = getattr(orchestrator, "document_extractor", None)
    if extractor is None:
        from ai.app.extraction.document_extractor import DocumentExtractor
        extractor = DocumentExtractor()

    if mime == "application/pdf":
        doc_payload = extractor.extract_from_pdf_bytes(content, doc_id)
    elif mime in ("image/png", "image/jpeg", "image/jpg"):
        try:
            doc_payload = extractor.extract_from_image(content, doc_id)
        except Exception:
            # Fallback when OCR runtime is not installed
            doc_payload = extractor.extract_from_text(f"[Image attachment: {file.filename}]", doc_id)
    else:
        doc_payload = extractor.extract_from_text(text_content, doc_id)

    input_event = OrchestrationInputEvent(
        event_type=CaseEventType.DOCUMENT_ATTACHED,
        documents=[doc_payload],
        actor=principal.principal_id,
        source=f"upload:{file.filename}",
        metadata={"description": description},
        reference_date=date.today(),
    )

    turn_result = await orchestrator.process_turn(
        case_id=case_id,
        input_event=input_event,
        expected_version=expected_version,
        idempotency_key=idempotency_key_header,
    )

    ws_mgr = _get_ws_manager(request)
    await ws_mgr.broadcast_turn_events(case_id, turn_result)

    return map_turn_result_to_view(turn_result)
