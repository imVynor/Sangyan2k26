import pytest
from crudauth import Principal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.auth.dependencies import get_current_principal, get_current_user
from src.interfaces.main import app
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
