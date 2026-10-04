from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from ...infrastructure.dependencies import AsyncSessionDep, CurrentUserDep
from .models import Grievance
from .schemas import GrievanceCreate, GrievanceRead

router = APIRouter(tags=["Grievances"])


def _snapshot_values(payload: GrievanceCreate) -> dict[str, Any]:
    return {
        "title": payload.title,
        "step": payload.step,
        "messages": [message.model_dump(by_alias=True) for message in payload.messages],
        "entries": [entry.model_dump() for entry in payload.entries],
    }


async def _owned_grievance(db: AsyncSessionDep, grievance_id: int, user_id: int) -> Grievance:
    result = await db.execute(
        select(Grievance).where(Grievance.id == grievance_id, Grievance.user_id == user_id)
    )
    grievance = result.scalar_one_or_none()
    if grievance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grievance not found")
    return grievance


@router.post("/", response_model=GrievanceRead, status_code=status.HTTP_201_CREATED)
async def create_grievance(
    payload: GrievanceCreate,
    current_user: CurrentUserDep,
    db: AsyncSessionDep,
) -> Grievance:
    grievance = Grievance(user_id=current_user["id"], **_snapshot_values(payload))
    db.add(grievance)
    await db.commit()
    await db.refresh(grievance)
    return grievance


@router.get("/", response_model=list[GrievanceRead])
async def list_grievances(
    current_user: CurrentUserDep,
    db: AsyncSessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Grievance]:
    result = await db.execute(
        select(Grievance)
        .where(Grievance.user_id == current_user["id"])
        .order_by(Grievance.updated_at.desc(), Grievance.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{grievance_id}", response_model=GrievanceRead)
async def get_grievance(
    grievance_id: int,
    current_user: CurrentUserDep,
    db: AsyncSessionDep,
) -> Grievance:
    return await _owned_grievance(db, grievance_id, current_user["id"])


@router.put("/{grievance_id}", response_model=GrievanceRead)
async def update_grievance(
    grievance_id: int,
    payload: GrievanceCreate,
    current_user: CurrentUserDep,
    db: AsyncSessionDep,
) -> Grievance:
    grievance = await _owned_grievance(db, grievance_id, current_user["id"])
    for key, value in _snapshot_values(payload).items():
        setattr(grievance, key, value)
    grievance.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(grievance)
    return grievance


@router.delete("/{grievance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grievance(
    grievance_id: int,
    current_user: CurrentUserDep,
    db: AsyncSessionDep,
) -> Response:
    grievance = await _owned_grievance(db, grievance_id, current_user["id"])
    await db.delete(grievance)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
