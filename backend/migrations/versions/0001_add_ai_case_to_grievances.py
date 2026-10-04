"""Persist AI case references on saved grievances.

Revision ID: 0001_add_ai_case_to_grievances
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_add_ai_case_to_grievances"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("grievances"):
        return

    columns = {column["name"] for column in inspector.get_columns("grievances")}
    if "ai_case_id" not in columns:
        op.add_column("grievances", sa.Column("ai_case_id", sa.String(length=32), nullable=True))
    if "ai_version" not in columns:
        op.add_column("grievances", sa.Column("ai_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("grievances"):
        return

    columns = {column["name"] for column in inspector.get_columns("grievances")}
    if "ai_version" in columns:
        op.drop_column("grievances", "ai_version")
    if "ai_case_id" in columns:
        op.drop_column("grievances", "ai_case_id")
