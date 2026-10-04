"""Add case state, events, evidence, assessments, and clarification tables for SANGYAN.

Revision ID: 004_case_state_and_dialogue
Revises: 003_hybrid_retrieval
Create Date: 2026-10-04 15:00:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_case_state_and_dialogue"
down_revision: Union[str, None] = "003_hybrid_retrieval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONType = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    # 1. cases
    op.create_table(
        "cases",
        sa.Column("case_id", sa.String(128), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(64), nullable=False, server_default="OPEN"),
        sa.Column("facts", JSONType, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("hypotheses", JSONType, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("declined_fields", JSONType, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("clarification_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. case_events
    op.create_table(
        "case_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("case_id", sa.String(128), sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", JSONType, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("actor", sa.String(64), nullable=False, server_default="SYSTEM"),
        sa.Column("source", sa.String(128), nullable=False, server_default="web"),
        sa.Column("idempotency_key", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_case_events_case_idempotency"),
    )
    op.create_index("ix_case_events_case_id", "case_events", ["case_id"])
    op.create_index("ix_case_events_created_at", "case_events", ["created_at"])
    op.create_index("ix_case_events_idempotency_key", "case_events", ["idempotency_key"])

    # 3. case_evidence
    op.create_table(
        "case_evidence",
        sa.Column("evidence_id", sa.String(128), primary_key=True),
        sa.Column("case_id", sa.String(128), sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_type", sa.String(64), nullable=False),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column("value", JSONType, nullable=True),
        sa.Column("source", sa.String(256), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.String(64), nullable=False, server_default="HIGH_SUPPORT"),
        sa.Column("provenance", JSONType, nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_case_evidence_case_id", "case_evidence", ["case_id"])
    op.create_index("ix_case_evidence_field_name", "case_evidence", ["field_name"])

    # 4. case_assessments
    op.create_table(
        "case_assessments",
        sa.Column("snapshot_id", sa.String(128), primary_key=True),
        sa.Column("case_id", sa.String(128), sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("findings", JSONType, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evaluated_provisions", JSONType, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evidence_requirements", JSONType, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("missing_information", JSONType, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("trigger_event_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_case_assessments_case_id", "case_assessments", ["case_id"])
    op.create_index("ix_case_assessments_created_at", "case_assessments", ["created_at"])

    # 5. clarification_questions
    op.create_table(
        "clarification_questions",
        sa.Column("question_id", sa.String(128), primary_key=True),
        sa.Column("case_id", sa.String(128), sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(32), nullable=False, server_default="HIGH"),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("expected_answer_type", sa.String(64), nullable=False, server_default="STRING"),
        sa.Column("multilingual_text", JSONType, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_clarification_questions_case_id", "clarification_questions", ["case_id"])


def downgrade() -> None:
    op.drop_table("clarification_questions")
    op.drop_table("case_assessments")
    op.drop_table("case_evidence")
    op.drop_table("case_events")
    op.drop_table("cases")
