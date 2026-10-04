from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ...infrastructure.database.models import TimestampMixin
from ...infrastructure.database.session import Base


class Grievance(Base, TimestampMixin):
    """A user's guided grievance workflow and its report state."""

    __tablename__ = "grievances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, init=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    step: Mapped[int] = mapped_column(Integer, default=0)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default_factory=list)
    entries: Mapped[list[dict[str, str]]] = mapped_column(JSON, default_factory=list)
