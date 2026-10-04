from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    speaker: Literal["user", "ai"] = Field(alias="from")
    text: str = Field(min_length=1, max_length=10_000)


class ReportEntry(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=10_000)


class GrievanceSnapshot(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    step: int = Field(ge=0, le=500)
    messages: list[ConversationMessage] = Field(max_length=500)
    entries: list[ReportEntry] = Field(max_length=100)


class GrievanceCreate(GrievanceSnapshot):
    pass


class GrievanceRead(GrievanceSnapshot):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime | None
