"""Provenance tracking for all SANGYAN knowledge artifacts.

Epistemic foundation:
Every knowledge object must preserve provenance to answer:
"Where exactly did this knowledge come from?"
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field, HttpUrl, field_validator

from ai.app.knowledge.source_classes import SourceClass


class Provenance(BaseModel):
    """Immutable audit trail of knowledge origin."""
    source_url: HttpUrl = Field(
        description="Canonical web origin of the official gazette, circular, or policy document."
    )
    document_id: str = Field(
        min_length=1,
        description="Unique identifier of the parent document."
    )
    source_hash: str = Field(
        min_length=8,
        description="Cryptographic hash (e.g. SHA-256) of raw content at ingestion time."
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when document content was retrieved."
    )
    source_class: SourceClass = Field(
        description="Categorical source class (REGULATORY, ORGANISATION_POLICY, etc.)."
    )
    extractor_version: str | None = Field(
        default=None,
        description="Ingestion pipeline or contract version responsible for extraction."
    )

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("document_id cannot be blank or whitespace.")
        return trimmed

    @field_validator("source_hash")
    @classmethod
    def validate_hash(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 8:
            raise ValueError("source_hash must be at least 8 characters.")
        return trimmed
