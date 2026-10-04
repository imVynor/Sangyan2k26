"""Use pgvector for provision embeddings.

Revision ID: 005_pgvector_embeddings
Revises: 004_case_state_and_dialogue
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "005_pgvector_embeddings"
down_revision: Union[str, None] = "004_case_state_and_dialogue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    inspector = sa.inspect(bind)
    if not inspector.has_table("knowledge_provision_embeddings"):
        return

    columns = {
        column["name"]: column["type"]
        for column in inspector.get_columns("knowledge_provision_embeddings")
    }
    embedding_type = columns.get("embedding")
    if isinstance(embedding_type, postgresql.ARRAY):
        op.alter_column(
            "knowledge_provision_embeddings",
            "embedding",
            existing_type=embedding_type,
            type_=Vector(768),
            existing_nullable=False,
            postgresql_using="('[' || array_to_string(embedding, ',') || ']')::vector(768)",
        )
    elif not isinstance(embedding_type, Vector):
        raise RuntimeError(
            "Expected knowledge_provision_embeddings.embedding to be a float array "
            "or pgvector column; migration stopped without changing the column."
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_provision_embeddings_hnsw "
        "ON knowledge_provision_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    if not inspector.has_table("knowledge_provision_embeddings"):
        return

    indexes = {
        index["name"]
        for index in inspector.get_indexes("knowledge_provision_embeddings")
    }
    if "ix_knowledge_provision_embeddings_hnsw" in indexes:
        op.drop_index(
            "ix_knowledge_provision_embeddings_hnsw",
            table_name="knowledge_provision_embeddings",
        )

    columns = {
        column["name"]: column["type"]
        for column in inspector.get_columns("knowledge_provision_embeddings")
    }
    embedding_type = columns.get("embedding")
    if isinstance(embedding_type, Vector):
        op.alter_column(
            "knowledge_provision_embeddings",
            "embedding",
            existing_type=embedding_type,
            type_=postgresql.ARRAY(sa.Float()),
            existing_nullable=False,
            postgresql_using="string_to_array(trim(both '[]' from embedding::text), ',')::double precision[]",
        )
