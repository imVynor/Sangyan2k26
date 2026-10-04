"""SQLAlchemy ORM models for SANGYAN Case State, Events, and Clarification.

Persists:
1. cases
2. case_events
3. case_facts
4. case_evidence
5. case_assessments
6. clarification_questions
"""

from datetime import datetime
from typing import Any
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai.app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class CaseORM(Base):
    """Relational table for a persistent investor grievance case."""
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="OPEN")
    facts: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    hypotheses: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    declined_fields: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    clarification_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    events: Mapped[list["CaseEventORM"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseEventORM.created_at",
    )
    evidence_records: Mapped[list["CaseEvidenceORM"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )
    assessments: Mapped[list["CaseAssessmentORM"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseAssessmentORM.created_at",
    )
    questions: Mapped[list["ClarificationQuestionORM"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )


class CaseEventORM(Base):
    """Append-only event store for case interactions and state transitions."""
    __tablename__ = "case_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="web")
    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    case: Mapped["CaseORM"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_case_events_case_version", "case_id", "case_version"),
        UniqueConstraint("case_id", "idempotency_key", name="uq_case_events_case_idempotency"),
    )


class CaseEvidenceORM(Base):
    """Individual empirical evidence records tied to a case."""
    __tablename__ = "case_evidence"

    evidence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value: Mapped[Any] = mapped_column(JSONType, nullable=True)
    source: Mapped[str] = mapped_column(String(256), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[str] = mapped_column(String(64), nullable=False, default="HIGH_SUPPORT")
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    case: Mapped["CaseORM"] = relationship(back_populates="evidence_records")


class CaseAssessmentORM(Base):
    """Point-in-time assessment snapshot evaluations."""
    __tablename__ = "case_assessments"

    snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    evaluated_provisions: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    evidence_requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    missing_information: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    trigger_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    case: Mapped["CaseORM"] = relationship(back_populates="assessments")


class ClarificationQuestionORM(Base):
    """Pending or answered clarification questions issued to the citizen."""
    __tablename__ = "clarification_questions"

    question_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("cases.case_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="HIGH")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    expected_answer_type: Mapped[str] = mapped_column(String(64), nullable=False, default="STRING")
    multilingual_text: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    case: Mapped["CaseORM"] = relationship(back_populates="questions")
