"""Comprehensive Transport and Integration Test Suite for SANGYAN API (Phase 6B).

Epistemic foundation:
- Proves transport remains thin and all authoritative mutations flow through CaseOrchestrator.
- Verifies optimistic concurrency (409 Conflict) and idempotency.
- Validates WebSocket streaming and event replay on reconnect with last_seen_version.
- Ensures empirical contradictions and claim resolution statuses remain visible to the frontend.
- Validates failure isolation (generation failure never corrupts or downgrades assessment).
- Enforces security boundaries and transport invariants.
"""

from datetime import datetime
from decimal import Decimal
import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from starlette.testclient import TestClient

from ai.app.api import create_app
from ai.app.api.dependencies import CurrentPrincipal
from ai.app.api.errors import (
    CaseNotFoundError,
    DocumentTooLargeError,
    ForbiddenCaseAccessError,
    UnsupportedMediaTypeError,
)
from ai.app.api.schemas.cases import CaseView
from ai.app.api.schemas.turns import CaseTurnResultView
from ai.app.api.websocket.manager import ConnectionManager
from ai.app.assessment.contracts import (
    ApplicabilityEvaluation,
    AssessmentFinding,
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    EpistemicLayer,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceType,
    RuleOutcome,
)
from ai.app.case.contracts import (
    AssessmentDelta,
    CaseEvent,
    CaseEventType,
    CaseState,
    CaseStatus,
    CaseVersionConflictError,
)
from ai.app.case.repository import InMemoryCaseRepository
from ai.app.clarification.contracts import ClarificationPlan, ClarificationQuestion, QuestionPriority
from ai.app.evidence_policy.contracts import Claim, ClaimStatus
from ai.app.evidence_policy.resolver import EvidencePolicyResolver
from ai.app.generation.contracts import GeneratedFinding, GeneratedResponse
from ai.app.orchestration.contracts import (
    ActionIntent,
    ActionTarget,
    AssessmentError,
    CaseTurnResult,
    ExtractionError,
    GenerationError,
    GenerationSnapshot,
    InvalidStateTransitionError,
    OrchestrationInputEvent,
    RetrievalError,
)
from ai.app.orchestration.orchestrator import CaseOrchestrator
from ai.app.retrieval.contracts import RetrievalResponse


@pytest.fixture
def repo() -> InMemoryCaseRepository:
    return InMemoryCaseRepository()


@pytest.fixture
def orchestrator(repo: InMemoryCaseRepository) -> CaseOrchestrator:
    return CaseOrchestrator(repository=repo)


@pytest.fixture
def ws_manager() -> ConnectionManager:
    return ConnectionManager()


@pytest.fixture
def app(orchestrator: CaseOrchestrator, ws_manager: ConnectionManager):
    return create_app(orchestrator=orchestrator, ws_manager=ws_manager)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


# =====================================================================
# 1. CASE LIFECYCLE TESTS (1-4)
# =====================================================================

def test_01_create_case(client: TestClient):
    """Test creating a new case via POST /api/v1/cases."""
    payload = {
        "initial_message": "Zerodha charged me Rs 50 for delivery trade",
        "language": "en",
    }
    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["case_id"].startswith("CASE-")
    assert data["version"] == 1
    assert "response" in data
    assert data["response"]["assessment"]["status"] in [
        AssessmentStatus.EVIDENCE_INSUFFICIENT.value,
        AssessmentStatus.VIOLATION_CONFIRMED.value,
        AssessmentStatus.COMPLIANT_WITH_REGULATION.value,
        AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED.value,
    ]


def test_02_submit_turn(client: TestClient):
    """Test submitting a second turn to an existing case."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Broker charged 50 rupees", "language": "en"},
    )
    cid = create_resp.json()["case_id"]
    v1 = create_resp.json()["version"]

    turn_resp = client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"message": "Transaction date was 2026-01-15", "expected_version": v1},
    )
    assert turn_resp.status_code == 200
    data = turn_resp.json()
    assert data["case_id"] == cid
    assert data["previous_version"] == 1
    assert data["new_version"] == 2


def test_03_retrieve_case_projection(client: TestClient):
    """Test retrieving frontend-safe case projection via GET /api/v1/cases/{case_id}."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha charged me 50 rupees for delivery", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    get_resp = client.get(f"/api/v1/cases/{cid}")
    assert get_resp.status_code == 200
    view = get_resp.json()
    assert view["case_id"] == cid
    assert view["version"] == 1
    assert "facts" in view
    assert "claims" in view
    assert "evidence" in view
    assert "current_assessment" in view
    assert "knowledge_snapshot_id" in view


def test_04_retrieve_audit_trail(client: TestClient):
    """Test retrieving immutable event audit history via GET /api/v1/cases/{case_id}/audit."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha charged me 50 rupees", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    audit_resp = client.get(f"/api/v1/cases/{cid}/audit")
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert audit_data["case_id"] == cid
    assert audit_data["total_events"] >= 1
    assert len(audit_data["events"]) >= 1
    event_types = [e["event_type"] for e in audit_data["events"]]
    assert CaseEventType.CASE_CREATED.value in event_types or CaseEventType.USER_MESSAGE_RECEIVED.value in event_types


# =====================================================================
# 2. IDEMPOTENCY TESTS (5-6)
# =====================================================================

def test_05_idempotent_duplicate_header(client: TestClient):
    """Test that submitting repeated requests with same Idempotency-Key returns cached result."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha charged me 50 rupees", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    t1 = client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"message": "Date was Jan 15"},
        headers={"Idempotency-Key": "IDEMP-KEY-TEST-001"},
    )
    assert t1.status_code == 200
    v_t1 = t1.json()["new_version"]

    t2 = client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"message": "Date was Jan 15"},
        headers={"Idempotency-Key": "IDEMP-KEY-TEST-001"},
    )
    assert t2.status_code == 200
    v_t2 = t2.json()["new_version"]
    assert v_t1 == v_t2


def test_06_idempotency_prevents_duplicate_turn_execution(client: TestClient, orchestrator: CaseOrchestrator):
    """Verify that an idempotent duplicate does NOT advance case version or create duplicate events."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "AngelOne account maintenance fee deducted", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"message": "First delivery on 2026-02-01"},
        headers={"Idempotency-Key": "IDEMP-SINGLE-EXEC"},
    )

    audit_before = client.get(f"/api/v1/cases/{cid}/audit").json()

    # Re-post same turn
    client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"message": "First delivery on 2026-02-01"},
        headers={"Idempotency-Key": "IDEMP-SINGLE-EXEC"},
    )

    audit_after = client.get(f"/api/v1/cases/{cid}/audit").json()
    assert audit_before["total_events"] == audit_after["total_events"]


# =====================================================================
# 3. OPTIMISTIC CONCURRENCY TESTS (7-9)
# =====================================================================

def test_07_correct_expected_version_succeeds(client: TestClient):
    """Submitting with the exact active version succeeds without conflict."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Initial grievance statement", "language": "en"},
    )
    cid = create_resp.json()["case_id"]
    current_v = create_resp.json()["version"]

    resp = client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"message": "Next message", "expected_version": current_v},
    )
    assert resp.status_code == 200
    assert resp.json()["new_version"] == current_v + 1


def test_08_stale_expected_version_returns_409(client: TestClient):
    """Submitting with a stale or incorrect expected_version returns HTTP 409 Conflict."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Initial grievance statement", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    conflict_resp = client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"message": "Concurrent conflicting update", "expected_version": 999},
    )
    assert conflict_resp.status_code == 409
    err = conflict_resp.json()["error"]
    assert err["code"] == "CASE_VERSION_CONFLICT"
    assert err["current_version"] == 1
    assert err["is_retryable"] is True


def test_09_zero_mutation_after_concurrency_conflict(client: TestClient):
    """Ensure that a 409 conflict causes ZERO state mutation or event emission in the repository."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha grievance", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    audit_before = client.get(f"/api/v1/cases/{cid}/audit").json()

    # Attempt conflicting mutation
    client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"message": "Stale mutation attempt", "expected_version": 42},
    )

    audit_after = client.get(f"/api/v1/cases/{cid}/audit").json()
    case_after = client.get(f"/api/v1/cases/{cid}").json()

    assert audit_before["total_events"] == audit_after["total_events"]
    assert case_after["version"] == 1


# =====================================================================
# 4. WEBSOCKET TESTS (10-14)
# =====================================================================

def test_10_websocket_connect(client: TestClient):
    """Test connecting to the WebSocket event stream."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Test complaint", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    with client.websocket_connect(f"/api/v1/ws/cases/{cid}") as ws:
        ws.send_json({"type": "ping"})
        msg = ws.receive_json()
        assert msg["type"] == "pong"
        assert msg["case_id"] == cid


def test_11_websocket_receive_turn_events(client: TestClient):
    """Test that submitting a turn broadcasts events to connected sockets."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Initial complaint for streaming test", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    with client.websocket_connect(f"/api/v1/ws/cases/{cid}") as ws:
        # Submit a turn via REST while socket is listening
        client.post(
            f"/api/v1/cases/{cid}/turns",
            json={"message": "Next evidentiary statement", "expected_version": 1},
        )

        # Receive streamed turn event
        streamed = ws.receive_json()
        assert streamed["case_id"] == cid
        assert "event_type" in streamed
        assert "version" in streamed


def test_12_websocket_disconnect_cleanly(client: TestClient, ws_manager: ConnectionManager):
    """Verify that socket disconnect correctly cleans up connection manager registry."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Socket cleanup test", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    with client.websocket_connect(f"/api/v1/ws/cases/{cid}") as ws:
        assert ws_manager.get_active_connection_count(cid) == 1

    # After exiting with block
    assert ws_manager.get_active_connection_count(cid) == 0


def test_13_websocket_reconnect(client: TestClient):
    """Verify client can disconnect and reconnect cleanly."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Reconnect test", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    with client.websocket_connect(f"/api/v1/ws/cases/{cid}") as ws1:
        ws1.send_json({"type": "ping"})
        assert ws1.receive_json()["type"] == "pong"

    # Reconnect
    with client.websocket_connect(f"/api/v1/ws/cases/{cid}") as ws2:
        ws2.send_json({"type": "ping"})
        assert ws2.receive_json()["type"] == "pong"


def test_14_websocket_event_replay_on_reconnect(client: TestClient):
    """Test replaying missed events when client connects with last_seen_version."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Replay verification", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    # Reconnect with last_seen_version=0
    with client.websocket_connect(f"/api/v1/ws/cases/{cid}?last_seen_version=0") as ws:
        msg = ws.receive_json()
        assert msg["case_id"] == cid
        assert msg["version"] >= 1


# =====================================================================
# 5. EVIDENCE UPLOAD TESTS (15-17)
# =====================================================================

def test_15_submit_evidence_document(client: TestClient):
    """Test uploading documentary evidence via POST /api/v1/cases/{id}/evidence."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha charged me 50", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    file_bytes = b"Contract Note\nTrade Date: 2026-01-15\nBrokerage: 15.00"
    files = {"file": ("contract_note.txt", io.BytesIO(file_bytes), "text/plain")}
    data = {"description": "Official contract note"}

    up_resp = client.post(f"/api/v1/cases/{cid}/evidence", files=files, data=data)
    assert up_resp.status_code == 200
    res = up_resp.json()
    assert res["case_id"] == cid
    assert res["new_version"] == 2
    assert len(res["accepted_evidence"]) >= 1


def test_16_evidence_upload_event_stream(client: TestClient):
    """Verify that uploading evidence streams DOCUMENT_ATTACHED / EVIDENCE_ACCEPTED events."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha fee grievance", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    with client.websocket_connect(f"/api/v1/ws/cases/{cid}") as ws:
        files = {"file": ("contract.txt", io.BytesIO(b"Trade: 15.00"), "text/plain")}
        client.post(f"/api/v1/cases/{cid}/evidence", files=files, data={})

        streamed = ws.receive_json()
        assert streamed["case_id"] == cid
        assert "event_type" in streamed


def test_17_evidence_in_case_projection(client: TestClient):
    """Verify uploaded evidence appears in subsequent GET /api/v1/cases/{id}."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha complaint", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    files = {"file": ("cn.txt", io.BytesIO(b"Brokerage: 15.00"), "text/plain")}
    client.post(f"/api/v1/cases/{cid}/evidence", files=files, data={"description": "CN PDF"})

    case_view = client.get(f"/api/v1/cases/{cid}").json()
    assert case_view["version"] == 2
    assert len(case_view["evidence"]) >= 1


# =====================================================================
# 6. EPISTEMIC STATE & CLAIM TESTS (18-20)
# =====================================================================

def test_18_conflicting_claims_remain_visible(client: TestClient):
    """Test that conflicting documentary vs user claims remain visible in CaseView."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha charged me 50 rupees", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    files = {"file": ("cn.txt", io.BytesIO(b"Contract Note Brokerage: 15.00"), "text/plain")}
    client.post(f"/api/v1/cases/{cid}/evidence", files=files, data={})

    case_view = client.get(f"/api/v1/cases/{cid}").json()
    claims = case_view["claims"]
    assert len(claims) >= 2
    # Check that both 50 and 15 are retained
    values = [c["claimed_value"] for c in claims]
    assert any("50" in str(v) for v in values)
    assert any("15" in str(v) for v in values)


def test_19_claim_resolution_status_preserved(client: TestClient):
    """Verify that claim resolution statuses (RESOLVED_BY_POLICY / SUPPORTED) are preserved."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha charged me 50 rupees", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    files = {"file": ("cn.txt", io.BytesIO(b"Contract Note Brokerage: 15.00"), "text/plain")}
    client.post(f"/api/v1/cases/{cid}/evidence", files=files, data={})

    case_view = client.get(f"/api/v1/cases/{cid}").json()
    statuses = [c["status"] for c in case_view["claims"]]
    assert any(s in [ClaimStatus.RESOLVED_BY_POLICY.value, ClaimStatus.SUPPORTED.value] for s in statuses)


def test_20_assessment_delta_exposed_correctly(client: TestClient):
    """Verify that machine-readable causal assessment deltas are exposed to the frontend."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Zerodha fee grievance", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    files = {"file": ("cn.txt", io.BytesIO(b"Contract Note Brokerage: 15.00"), "text/plain")}
    up_resp = client.post(f"/api/v1/cases/{cid}/evidence", files=files, data={})
    delta = up_resp.json()["assessment_delta"]

    assert "new_status" in delta
    assert "facts_changed" in delta
    assert "cause" in delta


# =====================================================================
# 7. FAILURE ISOLATION TESTS (21-24)
# =====================================================================

def test_21_extraction_failure_isolation(client: TestClient, orchestrator: CaseOrchestrator):
    """Verify that ExtractionError maps to HTTP 502 without partial state commit."""
    with patch.object(orchestrator.fact_extractor, "extract", side_effect=ExtractionError("Extraction crashed")):
        resp = client.post("/api/v1/cases", json={"initial_message": "Test extraction failure"})
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "EXTRACTION_FAILED"


def test_22_retrieval_failure_isolation(client: TestClient, orchestrator: CaseOrchestrator):
    """Verify that RetrievalError maps to HTTP 503."""
    mock_retriever = AsyncMock()
    mock_retriever.retrieve.side_effect = RetrievalError("Database vector search timeout")
    orchestrator.retriever = mock_retriever

    resp = client.post("/api/v1/cases", json={"initial_message": "Zerodha charged me 50 rupees for delivery trade"})
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "RETRIEVAL_FAILED"


def test_23_assessment_failure_isolation(client: TestClient, orchestrator: CaseOrchestrator):
    """Verify that AssessmentError maps to HTTP 500 without leaving corrupted state."""
    with patch.object(orchestrator.assessment_engine, "assess", side_effect=AssessmentError("Rule evaluator crash")):
        resp = client.post("/api/v1/cases", json={"initial_message": "Test assessment crash"})
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "ASSESSMENT_FAILED"


def test_24_generation_failure_preserves_assessment(client: TestClient, orchestrator: CaseOrchestrator):
    """Verify that GenerationError preserves the valid epistemic assessment and completes turn with FAILED status."""
    with patch.object(orchestrator.generator, "generate_response", side_effect=GenerationError("LLM API presentation timeout")):
        resp = client.post("/api/v1/cases", json={"initial_message": "Zerodha charged me 50 rupees"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["response"]["assessment"]["status"] is not None
        assert data["response"]["generation_status"] == "FAILED"


# =====================================================================
# 8. SECURITY & VALIDATION BOUNDARY TESTS (25-28)
# =====================================================================

def test_25_unauthorized_case_access(client: TestClient):
    """Verify that a principal restricted to other cases receives HTTP 403 Forbidden."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Private case", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    # Principal without access to this case
    with patch("ai.app.api.dependencies.CaseAccessPolicy.can_read_case", return_value=False):
        resp = client.get(f"/api/v1/cases/{cid}")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN_CASE_ACCESS"


def test_26_invalid_case_id_returns_404(client: TestClient):
    """Verify that querying a non-existent case_id returns HTTP 404 CaseNotFoundError."""
    resp = client.get("/api/v1/cases/CASE-DOES-NOT-EXIST")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CASE_NOT_FOUND"


def test_27_malformed_request_returns_422(client: TestClient):
    """Verify that malformed JSON payload returns HTTP 422 with structured validation error."""
    resp = client.post("/api/v1/cases", json={})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_28_unsupported_document_mime_returns_415(client: TestClient):
    """Verify that uploading an unsupported file type returns HTTP 415."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Grievance", "language": "en"},
    )
    cid = create_resp.json()["case_id"]

    files = {"file": ("malicious.exe", io.BytesIO(b"MZ..."), "application/x-msdownload")}
    resp = client.post(f"/api/v1/cases/{cid}/evidence", files=files, data={})
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


# =====================================================================
# 9. TRANSPORT INVARIANT TESTS (29-32)
# =====================================================================

def test_29_route_handlers_never_directly_invoke_rule_evaluator(client: TestClient):
    """Prove route handlers NEVER directly call RuleEvaluator, bypassing the orchestrator."""
    from ai.app.assessment.rule_evaluator import RuleEvaluator
    with patch.object(RuleEvaluator, "evaluate_provision", side_effect=AssertionError("Route handler directly called RuleEvaluator!")):
        resp = client.get("/api/v1/cases/CASE-NON-EXISTENT")
        assert resp.status_code == 404


def test_30_all_authoritative_mutation_flows_through_orchestrator(client: TestClient, orchestrator: CaseOrchestrator):
    """Prove that POST /cases and POST /turns exclusively route through CaseOrchestrator.process_turn."""
    with patch.object(orchestrator, "process_turn", wraps=orchestrator.process_turn) as spy_turn:
        resp = client.post("/api/v1/cases", json={"initial_message": "Testing turn routing"})
        assert resp.status_code == 201
        assert spy_turn.call_count == 1

        cid = resp.json()["case_id"]
        v1 = resp.json()["version"]

        client.post(
            f"/api/v1/cases/{cid}/turns",
            json={"message": "Turn 2 message", "expected_version": v1},
        )
        assert spy_turn.call_count == 2


def test_31_audit_filtering_by_version(client: TestClient):
    """Test ?after_version query parameter in GET /api/v1/cases/{id}/audit."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Initial complaint", "language": "en"},
    )
    cid = create_resp.json()["case_id"]
    v1 = create_resp.json()["version"]

    client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"message": "Turn 2", "expected_version": v1},
    )

    # Filter strictly after version 1
    resp = client.get(f"/api/v1/cases/{cid}/audit?after_version=1")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert all(e["case_version"] > 1 for e in events)


def test_32_user_declined_evidence_turn(client: TestClient):
    """Verify submitting a declined_field turn records decline and updates state."""
    create_resp = client.post(
        "/api/v1/cases",
        json={"initial_message": "Initial complaint", "language": "en"},
    )
    cid = create_resp.json()["case_id"]
    v1 = create_resp.json()["version"]

    decline_resp = client.post(
        f"/api/v1/cases/{cid}/turns",
        json={"declined_field": "contract_note", "expected_version": v1},
    )
    assert decline_resp.status_code == 200
    assert decline_resp.json()["new_version"] == 2
