"""Ingestion models and result schemas for SANGYAN knowledge pipeline."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl, model_validator

from ai.app.ingestion.errors import IngestionStage
from ai.app.knowledge.documents import (
    DocumentSection,
    NormalizedDocument,
    OrganisationDocument,
    RegulatoryDocument,
)
from ai.app.knowledge.source_classes import SourceClass


class IngestionStatus(str, Enum):
    """Canonical completion statuses for an ingestion request."""
    SUCCESS = "SUCCESS"
    DUPLICATE_CONTENT = "DUPLICATE_CONTENT"
    FETCH_FAILED = "FETCH_FAILED"
    UNSUPPORTED_CONTENT = "UNSUPPORTED_CONTENT"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    DOMAIN_VALIDATION_FAILED = "DOMAIN_VALIDATION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"


class IngestionRequest(BaseModel):
    """Specification for an official document ingestion job."""
    source_url: HttpUrl = Field(
        description="Public HTTP/HTTPS URL of the target regulatory or organisation document."
    )
    expected_domain: str | None = Field(
        default=None,
        description="Expected authoritative domain (e.g. 'sebi.gov.in', 'zerodha.com')."
    )
    source_class: SourceClass = Field(
        description="Categorical source class (REGULATORY, ORGANISATION_POLICY, etc.)."
    )
    organisation_id: str | None = Field(
        default=None,
        description="Mandatory for organisation sources; unique intermediary identifier."
    )
    authority: str | None = Field(
        default=None,
        description="Issuing regulatory body if known at request time (e.g. 'SEBI', 'NSE')."
    )
    document_type: str | None = Field(
        default=None,
        description="Circular, Policy, Fee Schedule, Notification, Master Circular."
    )
    force_reingest: bool = Field(
        default=False,
        description="If True, bypasses deduplication check and re-processes identical content."
    )

    @model_validator(mode="after")
    def validate_invariants(self) -> "IngestionRequest":
        """Enforce domain consistency rules."""
        if self.source_class.is_organisation:
            org_id = self.organisation_id.strip() if self.organisation_id else ""
            if not org_id:
                raise ValueError(
                    f"organisation_id is required and cannot be empty when source_class is '{self.source_class.value}'."
                )
        return self


class FetchedPayload(BaseModel):
    """Raw byte payload and transport-level metadata from fetcher."""
    raw_bytes: bytes
    final_url: HttpUrl
    http_status: int
    content_type: str
    retrieval_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_length: int


class ExtractedContent(BaseModel):
    """Deterministic structural output from HTML or PDF extractors."""
    title: str | None = None
    raw_text: str
    sections: list[DocumentSection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    page_count: int | None = None


class IngestionResult(BaseModel):
    """Structured response detailing the outcome of the ingestion pipeline."""
    success: bool
    status: IngestionStatus
    document_id: str | None = None
    source_hash: str | None = None
    document_type: str | None = None
    final_url: HttpUrl | None = None
    normalized_document: NormalizedDocument | None = None
    regulatory_document: RegulatoryDocument | None = None
    organisation_document: OrganisationDocument | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stage: IngestionStage | None = None
