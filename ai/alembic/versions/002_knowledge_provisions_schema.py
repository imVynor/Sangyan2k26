"""Add knowledge_provisions schema for SANGYAN Provision Extraction & Normalization.

Revision ID: 002_knowledge_provisions_schema
Revises: 001_initial_knowledge_schema
Create Date: 2026-10-04 02:40:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_knowledge_provisions_schema"
down_revision: Union[str, None] = "001_initial_knowledge_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    json_col = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    op.create_table(
        "knowledge_provisions",
        sa.Column("provision_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("section_id", sa.String(length=128), nullable=True),
        sa.Column("parent_provision_id", sa.String(length=128), nullable=True),
        sa.Column("provision_type", sa.String(length=64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=True),
        sa.Column("source_end", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("section_reference", sa.String(length=256), nullable=True),
        sa.Column("clause_reference", sa.String(length=256), nullable=True),
        sa.Column("authority", sa.String(length=128), nullable=True),
        sa.Column("organisation_id", sa.String(length=128), nullable=True),
        sa.Column("source_class", sa.String(length=64), nullable=False),
        sa.Column("topic", json_col, nullable=False, server_default="[]"),
        sa.Column("process", sa.String(length=128), nullable=True),
        sa.Column("applicable_entity", json_col, nullable=False, server_default="[]"),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("temporal_status", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("conditions_json", json_col, nullable=False, server_default="[]"),
        sa.Column("exceptions_json", json_col, nullable=False, server_default="[]"),
        sa.Column("procedures_json", json_col, nullable=False, server_default="[]"),
        sa.Column("timelines_json", json_col, nullable=False, server_default="[]"),
        sa.Column("fees_json", json_col, nullable=False, server_default="[]"),
        sa.Column("definitions_json", json_col, nullable=False, server_default="[]"),
        sa.Column("cross_references_json", json_col, nullable=False, server_default="[]"),
        sa.Column("provenance_json", json_col, nullable=False, server_default="{}"),
        sa.Column("extraction_metadata", json_col, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_knowledge_provisions_document_id", "knowledge_provisions", ["document_id"])
    op.create_index("ix_knowledge_provisions_section_id", "knowledge_provisions", ["section_id"])
    op.create_index("ix_knowledge_provisions_parent_provision_id", "knowledge_provisions", ["parent_provision_id"])
    op.create_index("ix_knowledge_provisions_provision_type", "knowledge_provisions", ["provision_type"])
    op.create_index("ix_knowledge_provisions_authority", "knowledge_provisions", ["authority"])
    op.create_index("ix_knowledge_provisions_organisation_id", "knowledge_provisions", ["organisation_id"])
    op.create_index("ix_knowledge_provisions_source_class", "knowledge_provisions", ["source_class"])
    op.create_index("ix_knowledge_provisions_process", "knowledge_provisions", ["process"])
    op.create_index("ix_knowledge_provisions_effective_date", "knowledge_provisions", ["effective_date"])
    op.create_index("ix_knowledge_provisions_temporal_status", "knowledge_provisions", ["temporal_status"])
    op.create_index("ix_knowledge_prov_doc_type", "knowledge_provisions", ["document_id", "provision_type"])
    op.create_index("ix_knowledge_prov_auth_proc", "knowledge_provisions", ["authority", "process"])
    op.create_index("ix_knowledge_prov_org_proc", "knowledge_provisions", ["organisation_id", "process"])


def downgrade() -> None:
    op.drop_table("knowledge_provisions")
