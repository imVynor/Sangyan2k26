import pytest
import httpx
from crudauth import Principal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.infrastructure.auth.dependencies import get_current_principal, get_current_user
from src.interfaces.main import app
from src.modules.grievance import routes as grievance_routes
from src.modules.user.models import User

pytestmark = pytest.mark.asyncio


def _snapshot(title: str = "Unexplained broker deduction") -> dict:
    return {
        "title": title,
        "step": 0,
        "messages": [
            {"from": "user", "text": "A broker deducted money"},
            {"from": "ai", "text": "When did this happen?"},
        ],
        "entries": [{"title": "What happened", "text": "A broker deducted money"}],
    }


async def _use_user(user: User) -> None:
    user_data = {"id": user.id, "is_superuser": user.is_superuser}

    async def current_user():
        return user_data

    async def current_principal():
        return Principal(user_id=user.id, is_superuser=user.is_superuser)

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_current_principal] = current_principal


async def test_grievance_create_list_update_and_get(
    auth_client: AsyncClient,
):
    created = await auth_client.post("/api/v1/grievances/", json=_snapshot())
    assert created.status_code == 201
    created_data = created.json()
    assert created_data["title"] == "Unexplained broker deduction"
    assert created_data["messages"][0] == {"from": "user", "text": "A broker deducted money"}
    grievance_id = created_data["id"]

    updated_snapshot = _snapshot("Broker charge")
    updated_snapshot["step"] = 2
    updated_snapshot["messages"].append({"from": "user", "text": "20 September"})
    update = await auth_client.put(f"/api/v1/grievances/{grievance_id}", json=updated_snapshot)
    assert update.status_code == 200
    assert update.json()["step"] == 2
    assert update.json()["title"] == "Broker charge"
    assert len(update.json()["messages"]) == 3

    listed = await auth_client.get("/api/v1/grievances/")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [grievance_id]

    fetched = await auth_client.get(f"/api/v1/grievances/{grievance_id}")
    assert fetched.status_code == 200
    assert fetched.json()["entries"] == updated_snapshot["entries"]


async def test_grievance_is_only_visible_to_its_owner(
    client: AsyncClient,
    test_user: dict,
    test_user_2: dict,
    db_session: AsyncSession,
):
    owner = await db_session.get(User, test_user["id"])
    other_user = await db_session.get(User, test_user_2["id"])
    assert owner is not None
    assert other_user is not None

    await _use_user(owner)
    created = await client.post("/api/v1/grievances/", json=_snapshot())
    assert created.status_code == 201
    grievance_id = created.json()["id"]

    await _use_user(other_user)
    assert (await client.get(f"/api/v1/grievances/{grievance_id}")).status_code == 404
    assert (await client.put(f"/api/v1/grievances/{grievance_id}", json=_snapshot())).status_code == 404
    assert (await client.delete(f"/api/v1/grievances/{grievance_id}")).status_code == 404
    assert (await client.get("/api/v1/grievances/")).json() == []


async def test_grievance_endpoints_require_authentication(client: AsyncClient):
    assert (await client.get("/api/v1/grievances/")).status_code == 401
    assert (await client.post("/api/v1/grievances/", json=_snapshot())).status_code == 401


async def test_grievance_delete_removes_only_the_owned_record(auth_client: AsyncClient):
    created = await auth_client.post("/api/v1/grievances/", json=_snapshot())
    grievance_id = created.json()["id"]

    deleted = await auth_client.delete(f"/api/v1/grievances/{grievance_id}")
    assert deleted.status_code == 204
    assert (await auth_client.get(f"/api/v1/grievances/{grievance_id}")).status_code == 404


async def test_ai_grievance_start_and_turn_are_persisted(
    auth_client: AsyncClient,
    test_user: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, dict, int]] = []

    async def fake_ai_request(endpoint: str, payload: dict, user_id: int) -> dict:
        calls.append((endpoint, payload, user_id))
        if endpoint == "cases":
            return {
                "case_id": "CASE-12345678",
                "version": 1,
                "response": {
                    "explanation": "I will assess the deduction.",
                    "assessment": {"summary": "More evidence is needed.", "status": "EVIDENCE_INSUFFICIENT"},
                    "clarification_questions": [{"text": "On what date was the charge made?"}],
                    "action_intents": [],
                },
            }
        return {
            "case_id": "CASE-12345678",
            "new_version": 2,
            "explanation": "The date helps identify the applicable rules.",
            "assessment": {"summary": "The date is now recorded.", "status": "EVIDENCE_INSUFFICIENT"},
            "clarification_questions": [],
            "action_intents": [],
        }

    monkeypatch.setattr(grievance_routes, "_request_ai", fake_ai_request)

    started = await auth_client.post(
        "/api/v1/grievances/start",
        json={"initial_message": "My broker deducted money without explanation"},
    )
    assert started.status_code == 201
    grievance = started.json()
    assert grievance["ai_case_id"] == "CASE-12345678"
    assert grievance["ai_version"] == 1
    assert grievance["messages"][-1]["text"].startswith("I will assess")
    assert any(entry["title"] == "Assessment" for entry in grievance["entries"])

    submitted = await auth_client.post(
        f"/api/v1/grievances/{grievance['id']}/turns",
        json={"message": "It happened on 20 September"},
    )
    assert submitted.status_code == 200
    result = submitted.json()
    assert result["grievance"]["ai_version"] == 2
    assert result["grievance"]["messages"][-2] == {"from": "user", "text": "It happened on 20 September"}
    assert result["grievance"]["messages"][-1]["text"].startswith("The date helps")
    assert result["turn"]["new_version"] == 2
    assert calls[0][2] == test_user["id"]
    assert calls[1][1]["expected_version"] == 1


async def test_ai_error_envelope_message_is_forwarded(monkeypatch: pytest.MonkeyPatch):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            503,
            json={"error": {"code": "RETRIEVAL_FAILED", "message": "Ollama is unavailable"}},
            request=request,
        )
    )
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        grievance_routes.httpx,
        "AsyncClient",
        lambda timeout: real_client(transport=transport, timeout=timeout),
    )

    with pytest.raises(HTTPException) as error:
        await grievance_routes._request_ai("cases", {"initial_message": "test"}, 1)

    assert error.value.status_code == 503
    assert error.value.detail == "Ollama is unavailable"


async def test_ai_plain_text_error_is_forwarded(monkeypatch: pytest.MonkeyPatch):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            500,
            text="Internal Server Error",
            request=request,
        )
    )
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        grievance_routes.httpx,
        "AsyncClient",
        lambda timeout: real_client(transport=transport, timeout=timeout),
    )

    with pytest.raises(HTTPException) as error:
        await grievance_routes._request_ai("cases", {"initial_message": "test"}, 1)

    assert error.value.status_code == 500
    assert error.value.detail == "Internal Server Error"


async def test_legacy_grievance_cannot_submit_ai_turn(auth_client: AsyncClient):
    created = await auth_client.post("/api/v1/grievances/", json=_snapshot())
    grievance_id = created.json()["id"]

    response = await auth_client.post(
        f"/api/v1/grievances/{grievance_id}/turns",
        json={"message": "Continue this report"},
    )
    assert response.status_code == 409
