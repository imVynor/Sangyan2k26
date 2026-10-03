"""Add search_vector and knowledge_provision_embeddings schema for SANGYAN Hybrid Retrieval.

Revision ID: 003_hybrid_retrieval_and_embeddings
Revises: 002_knowledge_provisions_schema
Create Date: 2026-10-04 03:00:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_hybrid_retrieval"
down_revision: Union[str, None] = "002_knowledge_provisions_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add search_vector column to knowledge_provisions
    op.add_column(
        "knowledge_provisions",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR().with_variant(sa.Text(), "sqlite"),
            nullable=True,
        ),
    )

    # 2. Populate search_vector for existing rows in PostgreSQL
    op.execute(
        """
        UPDATE knowledge_provisions
        SET search_vector = to_tsvector(
            'english',
            coalesce(source_text, '') || ' ' ||
            coalesce(title, '') || ' ' ||
            coalesce(section_reference, '') || ' ' ||
            coalesce(clause_reference, '') || ' ' ||
            coalesce(authority, '') || ' ' ||
            coalesce(organisation_id, '') || ' ' ||
            coalesce(process, '') || ' ' ||
            coalesce(provision_type, '')
        )
        WHERE search_vector IS NULL;
        """
    )

    # 3. Create GIN index on search_vector
    op.create_index(
        "ix_knowledge_provisions_search_vector",
        "knowledge_provisions",
        ["search_vector"],
        postgresql_using="gin",
    )

    # 4. Create knowledge_provision_embeddings table
    op.create_table(
        "knowledge_provision_embeddings",
        sa.Column("id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column(
            "provision_id",
            sa.String(length=128),
            sa.ForeignKey("knowledge_provisions.provision_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "embedding",
            postgresql.ARRAY(sa.Float()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("embedding_model_id", sa.String(length=64), nullable=False),
        sa.Column("embedding_model_version", sa.String(length=64), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provision_id", "embedding_model_id", "embedding_model_version", name="uq_prov_emb_model"),
    )

    op.create_index(
        "ix_emb_model_version",
        "knowledge_provision_embeddings",
        ["embedding_model_id", "embedding_model_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_emb_model_version", table_name="knowledge_provision_embeddings")
    op.drop_table("knowledge_provision_embeddings")
    op.drop_index("ix_knowledge_provisions_search_vector", table_name="knowledge_provisions")
    op.drop_column("knowledge_provisions", "search_vector")
