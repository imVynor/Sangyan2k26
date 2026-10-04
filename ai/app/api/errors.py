"""API Error Hierarchy, Exceptions, and FastAPI Exception Handlers for SANGYAN.

Epistemic foundation:
- Maps internal orchestrator and domain errors to deterministic HTTP/WebSocket status codes.
- Distinguishes operational failures (502/503) from concurrency/state conflicts (409) and not found (404).
- Generation failures never destroy or downgrade epistemic assessments.
- Standardizes error envelopes with request correlation and retry flags.
"""

from typing import Any
import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ai.app.api.schemas.common import APIErrorResponse, ErrorDetail
from ai.app.case.contracts import CaseVersionConflictError
from ai.app.orchestration.contracts import (
    AssessmentError,
    DuplicateEventError,
    ExtractionError,
    GenerationError,
    InvalidStateTransitionError,
    OrchestrationError,
    RetrievalError,
)


class APIError(Exception):
    """Base exception for transport-layer failures."""
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
        case_id: str | None = None,
        turn_id: str | None = None,
        is_retryable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.case_id = case_id
        self.turn_id = turn_id
        self.is_retryable = is_retryable


class CaseNotFoundError(APIError):
    """Raised when a requested case_id does not exist."""
    def __init__(self, case_id: str):
        super().__init__(
            f"Case '{case_id}' was not found.",
            code="CASE_NOT_FOUND",
            status_code=404,
            case_id=case_id,
            is_retryable=False,
        )


class UnauthorizedError(APIError):
    """Raised when credentials or tokens are missing or invalid."""
    def __init__(self, message: str = "Authentication required."):
        super().__init__(message, code="UNAUTHORIZED", status_code=401, is_retryable=False)


class ForbiddenCaseAccessError(APIError):
    """Raised when a principal is denied access to a specific case."""
    def __init__(self, case_id: str, principal_id: str = "anonymous"):
        super().__init__(
            f"Principal '{principal_id}' is not authorized to access case '{case_id}'.",
            code="FORBIDDEN_CASE_ACCESS",
            status_code=403,
            case_id=case_id,
            is_retryable=False,
        )


class UnsupportedMediaTypeError(APIError):
    """Raised when an uploaded evidence document has an unsupported MIME type."""
    def __init__(self, mime_type: str, supported: list[str]):
        super().__init__(
            f"Unsupported document MIME type: '{mime_type}'. Supported: {supported}",
            code="UNSUPPORTED_MEDIA_TYPE",
            status_code=415,
            details={"mime_type": mime_type, "supported": supported},
            is_retryable=False,
        )


class DocumentTooLargeError(APIError):
    """Raised when an uploaded evidence document exceeds size limits."""
    def __init__(self, size_bytes: int, max_bytes: int):
        super().__init__(
            f"Document size {size_bytes} bytes exceeds maximum allowed limit of {max_bytes} bytes.",
            code="DOCUMENT_TOO_LARGE",
            status_code=413,
            details={"size_bytes": size_bytes, "max_bytes": max_bytes},
            is_retryable=False,
        )


def register_error_handlers(app: FastAPI) -> None:
    """Register custom exception handlers on the FastAPI application."""

    def _get_request_id(request: Request) -> str:
        return getattr(request.state, "request_id", None) or f"REQ-{uuid.uuid4().hex[:8].upper()}"

    @app.exception_handler(CaseNotFoundError)
    async def case_not_found_handler(request: Request, exc: CaseNotFoundError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                case_id=exc.case_id,
                details=exc.details,
                is_retryable=exc.is_retryable,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(ForbiddenCaseAccessError)
    async def forbidden_handler(request: Request, exc: ForbiddenCaseAccessError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                case_id=exc.case_id,
                details=exc.details,
                is_retryable=exc.is_retryable,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(CaseVersionConflictError)
    async def version_conflict_handler(request: Request, exc: CaseVersionConflictError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code="CASE_VERSION_CONFLICT",
                message=str(exc),
                current_version=exc.actual_version,
                details={"expected_version": exc.expected_version, "actual_version": exc.actual_version},
                is_retryable=True,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_transition_handler(request: Request, exc: InvalidStateTransitionError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code="INVALID_STATE_TRANSITION",
                message=str(exc),
                details=exc.details,
                is_retryable=exc.is_retryable,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    @app.exception_handler(DuplicateEventError)
    async def duplicate_event_handler(request: Request, exc: DuplicateEventError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code="DUPLICATE_EVENT",
                message=str(exc),
                details=exc.details,
                is_retryable=False,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    @app.exception_handler(ExtractionError)
    async def extraction_error_handler(request: Request, exc: ExtractionError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code="EXTRACTION_FAILED",
                message=str(exc),
                details=exc.details,
                is_retryable=exc.is_retryable,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=502, content=body.model_dump(mode="json"))

    @app.exception_handler(RetrievalError)
    async def retrieval_error_handler(request: Request, exc: RetrievalError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code="RETRIEVAL_FAILED",
                message=str(exc),
                details=exc.details,
                is_retryable=exc.is_retryable,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=503, content=body.model_dump(mode="json"))

    @app.exception_handler(AssessmentError)
    async def assessment_error_handler(request: Request, exc: AssessmentError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code="ASSESSMENT_FAILED",
                message=str(exc),
                details=exc.details,
                is_retryable=exc.is_retryable,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=500, content=body.model_dump(mode="json"))

    @app.exception_handler(GenerationError)
    async def generation_error_handler(request: Request, exc: GenerationError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code="GENERATION_FAILED",
                message=str(exc),
                details=exc.details,
                is_retryable=True,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=502, content=body.model_dump(mode="json"))

    @app.exception_handler(APIError)
    async def generic_api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                case_id=exc.case_id,
                turn_id=exc.turn_id,
                details=exc.details,
                is_retryable=exc.is_retryable,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        req_id = _get_request_id(request)
        body = APIErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request body or query parameter validation failed.",
                details={"errors": exc.errors()},
                is_retryable=False,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        req_id = _get_request_id(request)
        code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
        body = APIErrorResponse(
            error=ErrorDetail(
                code=code,
                message=str(exc.detail),
                is_retryable=False,
            ),
            request_id=req_id,
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))
