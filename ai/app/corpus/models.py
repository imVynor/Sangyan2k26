"""Corpus manifest data models and execution schemas for SANGYAN.

The corpus manifest is a reproducible acquisition specification describing which
external sources SANGYAN is allowed and expected to ingest.

Strict principles:
- Explicit sources only (no crawling, no spidering, no search engine discovery).
- Strongly typed and validated.
- Source contents are NOT embedded in manifest models.
- source_id must be non-empty, unique, and stable across revisions.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from ai.app.knowledge.source_classes import SourceClass


class SourceExecutionStatus(str, Enum):
    """Execution status for an individual manifest source entry."""
    SUCCESS = "SUCCESS"
    DUPLICATE = "DUPLICATE"
    FAILED = "FAILED"
    DRY_RUN = "DRY_RUN"


class CorpusSource(BaseModel):
    """Specification for an explicit authoritative knowledge source in the manifest.
    
    Contains acquisition metadata ONLY. Source content and extracted text are NEVER
    embedded in manifest models.
    """
    source_id: str = Field(
        description="Non-empty, unique, stable identifier for this knowledge source (e.g. 'sebi_investor_grievance')."
    )
    source_class: SourceClass = Field(
        description="Authoritative source class (REGULATORY, ORGANISATION_POLICY, etc.)."
    )
    url: HttpUrl = Field(
        description="Authoritative HTTP or HTTPS URL. Local paths and credentials are prohibited."
    )
    authority: str | None = Field(
        default=None,
        description="Regulatory or statutory issuing authority (e.g. 'SEBI', 'NSE')."
    )
    organisation_id: str | None = Field(
        default=None,
        description="Mandatory for organisation sources (e.g. 'ORG_ZERODHA')."
    )
    document_type: str | None = Field(
        default=None,
        description="Type classification (e.g. 'Circular', 'Policy', 'Fee Schedule')."
    )
    topic: list[str] | None = Field(
        default=None,
        description="List of domain topic tags associated with this source."
    )
    expected_domain: str | None = Field(
        default=None,
        description="Authoritative domain expected for redirect protection (e.g. 'sebi.gov.in')."
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of this source's purpose."
    )

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("source_id cannot be empty or blank whitespace.")
        return s

    @field_validator("topic", mode="before")
    @classmethod
    def normalize_topic(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return [stripped] if stripped else None
        if isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if str(item).strip()]
        return None

    @field_validator("expected_domain")
    @classmethod
    def normalize_expected_domain(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip().lower()
        if not s:
            return None
        if "/" in s or ":" in s:
            raise ValueError(f"expected_domain should be a plain domain (e.g. 'sebi.gov.in'), not a URL or path: '{v}'")
        return s

    @field_validator("url")
    @classmethod
    def validate_url_security(cls, v: HttpUrl) -> HttpUrl:
        if v.scheme not in {"http", "https"}:
            raise ValueError(f"URL scheme must be http or https, got '{v.scheme}'.")
        if v.username is not None or v.password is not None:
            raise ValueError("URL must not contain embedded user credentials.")
        if not v.host:
            raise ValueError("URL must have a valid host name.")
        return v

    @model_validator(mode="after")
    def validate_invariants(self) -> "CorpusSource":
        # Organisation sources MUST have non-empty organisation_id
        if self.source_class.is_organisation:
            org_id = self.organisation_id.strip() if self.organisation_id else ""
            if not org_id:
                raise ValueError(
                    f"organisation_id is required for source '{self.source_id}' with source_class '{self.source_class.value}'."
                )
        return self


class CorpusManifest(BaseModel):
    """Reproducible acquisition specification for SANGYAN knowledge corpus."""
    corpus_version: str = Field(
        description="Explicit version tag for this corpus manifest (e.g. '2026-10-04-v1')."
    )
    sources: list[CorpusSource] = Field(
        description="Explicit list of authoritative sources to be ingested."
    )

    @field_validator("corpus_version")
    @classmethod
    def validate_corpus_version(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("corpus_version cannot be empty or blank whitespace.")
        return s

    @model_validator(mode="after")
    def validate_manifest_rules(self) -> "CorpusManifest":
        if not self.sources:
            raise ValueError("Manifest must contain at least one source entry; sources list cannot be empty.")

        seen_ids: set[str] = set()
        duplicates: set[str] = set()
        for idx, src in enumerate(self.sources):
            if src.source_id in seen_ids:
                duplicates.add(src.source_id)
            seen_ids.add(src.source_id)

        if duplicates:
            sorted_dups = sorted(list(duplicates))
            raise ValueError(
                f"Duplicate source_id values detected in manifest: {', '.join(sorted_dups)}. Each source_id must be unique."
            )

        return self


class SourceRunResult(BaseModel):
    """Outcome for a single source entry processed during a corpus run."""
    source_id: str
    url: str
    status: str
    document_id: str | None = None
    source_hash: str | None = None
    error_stage: str | None = None
    error_message: str | None = None


class CorpusRunResult(BaseModel):
    """Structured report of a complete corpus ingestion execution."""
    corpus_version: str
    started_at: datetime
    completed_at: datetime
    total_sources: int
    successful_sources: int
    duplicate_sources: int
    failed_sources: int
    results: list[SourceRunResult]
