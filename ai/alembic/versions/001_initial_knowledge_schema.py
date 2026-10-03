"""Initial knowledge persistence schema for SANGYAN.

Revision ID: 001_initial_knowledge_schema
Revises: None
Create Date: 2026-10-04 01:30:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_knowledge_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. regulatory_documents
    op.create_table(
        "regulatory_documents",
        sa.Column("document_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("authority", sa.String(length=128), nullable=False),
        sa.Column("jurisdiction", sa.String(length=128), nullable=False, server_default="India"),
        sa.Column("document_type", sa.String(length=128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("document_identifier", sa.String(length=256), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("superseded_status", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_class", sa.String(length=64), nullable=False, server_default="REGULATORY"),
        sa.CheckConstraint("source_class = 'REGULATORY'", name="ck_regulatory_documents_check_regulatory_source_class"),
        sa.CheckConstraint(
            "termination_date IS NULL OR effective_date IS NULL OR termination_date >= effective_date",
            name="ck_regulatory_documents_check_regulatory_dates_order",
        ),
        sa.CheckConstraint(
            "superseded_status IN ('CURRENT', 'SUPERSEDED', 'PARTIALLY_AMENDED', 'UNKNOWN')",
            name="ck_regulatory_documents_check_regulatory_superseded_status",
        ),
    )
    op.create_index("ix_regulatory_documents_authority", "regulatory_documents", ["authority"])
    op.create_index("ix_regulatory_documents_document_identifier", "regulatory_documents", ["document_identifier"])
    op.create_index("ix_regulatory_documents_publication_date", "regulatory_documents", ["publication_date"])
    op.create_index("ix_regulatory_documents_effective_date", "regulatory_documents", ["effective_date"])
    op.create_index("ix_regulatory_documents_source_hash", "regulatory_documents", ["source_hash"])

    # 2. organisation_documents
    op.create_table(
        "organisation_documents",
        sa.Column("document_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.String(length=128), nullable=False),
        sa.Column("source_class", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("document_identifier", sa.String(length=256), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("superseded_status", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organisation_name", sa.String(length=256), nullable=True),
        sa.Column("applicable_process", sa.String(length=128), nullable=True),
        sa.Column("topic", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "source_class IN ('ORGANISATION_POLICY', 'ORGANISATION_PROCEDURE', 'ORGANISATION_FAQ')",
            name="ck_organisation_documents_check_org_source_class",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR effective_date IS NULL OR termination_date >= effective_date",
            name="ck_organisation_documents_check_org_dates_order",
        ),
        sa.CheckConstraint(
            "superseded_status IN ('CURRENT', 'SUPERSEDED', 'PARTIALLY_AMENDED', 'UNKNOWN')",
            name="ck_organisation_documents_check_org_superseded_status",
        ),
    )
    op.create_index("ix_organisation_documents_organisation_id", "organisation_documents", ["organisation_id"])
    op.create_index("ix_organisation_documents_source_hash", "organisation_documents", ["source_hash"])
    op.create_index("ix_organisation_documents_applicable_process", "organisation_documents", ["applicable_process"])

    # 3. provenance
    op.create_table(
        "provenance",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_class", sa.String(length=64), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("document_id", "source_hash", name="uq_provenance_doc_hash"),
    )
    op.create_index("ix_provenance_document_id", "provenance", ["document_id"])
    op.create_index("ix_provenance_source_hash", "provenance", ["source_hash"])

    # 4. document_sections
    op.create_table(
        "document_sections",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("section_key", sa.String(length=128), nullable=False),
        sa.Column(
            "parent_section_id",
            sa.BigInteger(),
            sa.ForeignKey("document_sections.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.UniqueConstraint("document_id", "section_key", name="uq_doc_sections_doc_key"),
    )
    op.create_index("ix_document_sections_document_id", "document_sections", ["document_id"])
    op.create_index("ix_document_sections_parent_section_id", "document_sections", ["parent_section_id"])
    op.create_index("ix_sections_doc_order", "document_sections", ["document_id", "order_index"])

    # 5. regulatory_provisions
    op.create_table(
        "regulatory_provisions",
        sa.Column("provision_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.String(length=128),
            sa.ForeignKey("regulatory_documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section", sa.String(length=256), nullable=True),
        sa.Column("clause", sa.String(length=256), nullable=True),
        sa.Column("paragraph", sa.String(length=256), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("definitions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("cross_references", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("superseded_status", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
    )
    op.create_index("ix_regulatory_provisions_document_id", "regulatory_provisions", ["document_id"])

    # 6. organisation_provisions
    op.create_table(
        "organisation_provisions",
        sa.Column("provision_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.String(length=128),
            sa.ForeignKey("organisation_documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organisation_id", sa.String(length=128), nullable=False),
        sa.Column("section", sa.String(length=256), nullable=True),
        sa.Column("clause", sa.String(length=256), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("applicable_process", sa.String(length=128), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("superseded_status", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
    )
    op.create_index("ix_organisation_provisions_document_id", "organisation_provisions", ["document_id"])
    op.create_index("ix_organisation_provisions_organisation_id", "organisation_provisions", ["organisation_id"])

    # 7. knowledge_relationships
    op.create_table(
        "knowledge_relationships",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("relationship_id", sa.String(length=128), nullable=True, unique=True),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.CheckConstraint("source_id != target_id", name="ck_knowledge_relationships_check_rel_source_target_distinct"),
        sa.CheckConstraint(
            "relationship_type IN ('AMENDMENT', 'SUPERSEDES', 'CROSS_REFERENCE', 'DEFINITION_OF', 'EXCEPTION_TO', 'PART_OF')",
            name="ck_knowledge_relationships_check_rel_type_allowed",
        ),
    )
    op.create_index("ix_knowledge_relationships_source_id", "knowledge_relationships", ["source_id"])
    op.create_index("ix_knowledge_relationships_target_id", "knowledge_relationships", ["target_id"])
    op.create_index("ix_knowledge_relationships_relationship_type", "knowledge_relationships", ["relationship_type"])

    # 8. ingestion_records
    op.create_table(
        "ingestion_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("ingestion_id", sa.String(length=128), primary_key=False, nullable=False, unique=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=True),
        sa.Column("ingestion_status", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_stage", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_ingestion_records_ingestion_id", "ingestion_records", ["ingestion_id"])
    op.create_index("ix_ingestion_records_source_hash", "ingestion_records", ["source_hash"])
    op.create_index("ix_ingestion_records_document_id", "ingestion_records", ["document_id"])
    op.create_index("ix_ingestion_records_ingestion_status", "ingestion_records", ["ingestion_status"])


def downgrade() -> None:
    # Drop tables in reverse topological order to respect foreign key constraints
    op.drop_table("ingestion_records")
    op.drop_table("knowledge_relationships")
    op.drop_table("organisation_provisions")
    op.drop_table("regulatory_provisions")
    op.drop_table("document_sections")
    op.drop_table("provenance")
    op.drop_table("organisation_documents")
    op.drop_table("regulatory_documents")
