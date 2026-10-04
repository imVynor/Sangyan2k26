"""Base metadata and declarative model foundation for SANGYAN PostgreSQL schema."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Explicit naming conventions for constraints, foreign keys, and indexes
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base class for all SANGYAN database models."""
    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)
