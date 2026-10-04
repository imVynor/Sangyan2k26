from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from ...infrastructure.config.settings import settings
from ...infrastructure.dependencies import AsyncSessionDep, CurrentUserDep
from .models import Grievance
from .schemas import (
    GrievanceCreate,
    GrievanceRead,
    GrievanceTurnResponse,
    StartGrievanceRequest,
    SubmitGrievanceTurnRequest,
)

router = APIRouter(tags=["Grievances"])


def _snapshot_values(payload: GrievanceCreate) -> dict[str, Any]:
    return {
        "title": payload.title,
        "step": payload.step,
        "messages": [message.model_dump(by_alias=True) for message in payload.messages],
        "entries": [entry.model_dump() for entry in payload.entries],
    }


async def _request_ai(
    endpoint: str,
    payload: dict[str, Any],
    user_id: int,
) -> dict[str, Any]:
    url = f"{settings.AI_BACKEND_URL.rstrip('/')}/api/v1/{endpoint.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=130.0) as client:
            response = await client.post(url, json=payload, headers={"X-User-ID": str(user_id)})
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The AI service timed out. Please retry your request.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is unavailable. Please try again shortly.",
        ) from exc

    if not response.is_success:
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("detail")
                if detail is None and isinstance(body.get("error"), dict):
                    detail = body["error"].get("message")
                if detail is None:
                    detail = "The AI service rejected the request."
            else:
                detail = body
        except ValueError:
            detail = response.text.strip() or f"The AI service returned HTTP {response.status_code} without an error detail."
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service returned an invalid response.",
        ) from exc

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service returned an invalid response.",
        )
    return result


def _assistant_reply(turn: dict[str, Any]) -> str:
    assessment = turn.get("assessment")
    if not isinstance(assessment, dict):
        assessment = {}

    explanation = turn.get("explanation")
    summary = assessment.get("summary")
    parts = [text.strip() for text in (explanation, summary) if isinstance(text, str) and text.strip()]

    questions = turn.get("clarification_questions", [])
    if isinstance(questions, list):
        question_texts = [
            question["text"].strip()
            for question in questions
            if isinstance(question, dict) and isinstance(question.get("text"), str) and question["text"].strip()
        ]
        if question_texts:
            parts.append("To assess this accurately, please clarify:\n" + "\n".join(f"- {text}" for text in question_texts))

    if not parts:
        assessment_status = assessment.get("status")
        if not isinstance(assessment_status, str) or not assessment_status:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The AI service did not return an explanation or assessment.",
            )
        parts.append(f"Current assessment status: {assessment_status}.")

    reply = "\n\n".join(parts)
    if len(reply) > 10_000:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service returned a response that exceeds the conversation limit.",
        )
    return reply


def _update_report_entries(
    entries: list[dict[str, str]],
    turn: dict[str, Any],
) -> list[dict[str, str]]:
    assessment = turn.get("assessment")
    if isinstance(assessment, dict):
        summary = assessment.get("summary")
        if isinstance(summary, str) and summary.strip():
            entries = _replace_report_entry(entries, "Assessment", summary.strip())

    questions = turn.get("clarification_questions")
    if isinstance(questions, list):
        items = [
            question["text"].strip()
            for question in questions
            if isinstance(question, dict) and isinstance(question.get("text"), str) and question["text"].strip()
        ]
        if items:
            entries = _replace_report_entry(entries, "Evidence needed", "\n".join(items))

    actions = turn.get("action_intents")
    if isinstance(actions, list):
        items = [
            action["rationale"].strip()
            for action in actions
            if isinstance(action, dict) and isinstance(action.get("rationale"), str) and action["rationale"].strip()
        ]
        if items:
            entries = _replace_report_entry(entries, "Suggested next steps", "\n".join(items))
    return entries


def _replace_report_entry(
    entries: list[dict[str, str]],
    title: str,
    text: str,
) -> list[dict[str, str]]:
    return [entry for entry in entries if entry.get("title") != title] + [{"title": title, "text": text[:10_000]}]


async def _owned_grievance(db: AsyncSessionDep, grievance_id: int, user_id: int) -> Grievance:
    result = await db.execute(
        select(Grievance).where(Grievance.id == grievance_id, Grievance.user_id == user_id)
    )
    grievance = result.scalar_one_or_none()
    if grievance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grievance not found")
    return grievance


@router.post("/start", response_model=GrievanceRead, status_code=status.HTTP_201_CREATED)
async def start_ai_grievance(
    payload: StartGrievanceRequest,
    current_user: CurrentUserDep,
    db: AsyncSessionDep,
) -> Grievance:
    result = await _request_ai(
        "cases",
        {"initial_message": payload.initial_message, "language": payload.language},
        current_user["id"],
    )
    ai_case_id = result.get("case_id")
    version = result.get("version")
    turn = result.get("response")
    if (
        not isinstance(ai_case_id, str)
        or not ai_case_id
        or not isinstance(version, int)
        or not isinstance(turn, dict)
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service returned an invalid case response.",
        )

    assistant_message = _assistant_reply(turn)
    grievance = Grievance(
        user_id=current_user["id"],
        title=payload.initial_message[:255],
        step=1,
        messages=[
            {"from": "user", "text": payload.initial_message},
            {"from": "ai", "text": assistant_message},
        ],
        entries=[{"title": "Problem details", "text": payload.initial_message}],
        ai_case_id=ai_case_id,
        ai_version=version,
    )
    grievance.entries = _update_report_entries(grievance.entries, turn)
    db.add(grievance)
    await db.commit()
    await db.refresh(grievance)
    return grievance


@router.post("/{grievance_id}/turns", response_model=GrievanceTurnResponse)
async def submit_ai_turn(
    grievance_id: int,
    payload: SubmitGrievanceTurnRequest,
    current_user: CurrentUserDep,
    db: AsyncSessionDep,
) -> GrievanceTurnResponse:
    grievance = await _owned_grievance(db, grievance_id, current_user["id"])
    if not grievance.ai_case_id or grievance.ai_version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This saved grievance does not have an AI case. Start a new grievance to use the AI assistant.",
        )
    if len(grievance.messages) > 498:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This conversation has reached its message limit. Start a new grievance to continue.",
        )

    turn = await _request_ai(
        f"cases/{grievance.ai_case_id}/turns",
        {
            "message": payload.message,
            "expected_version": grievance.ai_version,
            "language": payload.language,
        },
        current_user["id"],
    )
    new_version = turn.get("new_version")
    if turn.get("case_id") != grievance.ai_case_id or not isinstance(new_version, int):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service returned an invalid turn response.",
        )

    assistant_message = _assistant_reply(turn)
    grievance.messages = [
        *grievance.messages,
        {"from": "user", "text": payload.message},
        {"from": "ai", "text": assistant_message},
    ]
    grievance.entries = _update_report_entries(grievance.entries, turn)
    grievance.step += 1
    grievance.ai_version = new_version
    grievance.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(grievance)
    return GrievanceTurnResponse(grievance=GrievanceRead.model_validate(grievance), turn=turn)


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
