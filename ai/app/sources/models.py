"""Models and schemas for SANGYAN Official Source Registry.

The Source Registry represents WHERE knowledge comes from (acquisition specification),
as opposed to the Document Repository which stores WHAT was actually retrieved.

Epistemic foundation:
- Sources produce multiple versioned documents across time.
- Historical versions are preserved immutably.
- Bounded to explicitly registered official domains only.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from ai.app.knowledge.source_classes import SourceClass


class RefreshPolicy(str, Enum):
    """Frequency policy for source change detection."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MANUAL = "manual"


class DiscoveryMethod(str, Enum):
    """Permitted bounded discovery mechanisms."""
    EXPLICIT_URL = "explicit_url"
    INDEX_PAGE = "index_page"
    DOCUMENT_LIST = "document_list"
    SITEMAP = "sitemap"


class SourceStatus(str, Enum):
    """Lifecycle and health state of a registered source."""
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"
    UNAVAILABLE = "unavailable"


class SourceCheckStatus(str, Enum):
    """Outcome of a change detection check."""
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    NEW_DOCUMENT = "NEW_DOCUMENT"
    FETCH_FAILED = "FETCH_FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    MALICIOUS_REDIRECT = "MALICIOUS_REDIRECT"


class SourceRegistryEntry(BaseModel):
    """Authoritative source registration."""
    source_id: str = Field(
        description="Unique, stable identifier for this knowledge source (e.g. 'sebi_stock_broker_master_circular')."
    )
    authority: str | None = Field(
        default=None,
        description="Regulatory or statutory authority (e.g. 'SEBI', 'NSE', 'CDSL')."
    )
    organisation_id: str | None = Field(
        default=None,
        description="Intermediary identifier if organisation source (e.g. 'ORG_ZERODHA')."
    )
    source_class: SourceClass = Field(
        description="Authoritative source class (REGULATORY, ORGANISATION_POLICY, etc.)."
    )
    canonical_url: HttpUrl = Field(
        description="Authoritative HTTPS URL where documents or listings reside."
    )
    expected_domain: str = Field(
        description="Strict expected domain for SSRF and redirect protection (e.g. 'sebi.gov.in')."
    )
    document_type: str | None = Field(
        default=None,
        description="Circular, Master Circular, Tariff Schedule, Grievance Procedure, etc."
    )
    topic: list[str] = Field(
        default_factory=list,
        description="Domain topic tags (e.g. ['stock_broker', 'investor_grievance', 'dp_charges'])."
    )
    discovery_method: DiscoveryMethod = Field(
        default=DiscoveryMethod.EXPLICIT_URL,
        description="Allowed discovery mechanism for this source."
    )
    active: bool = Field(
        default=True,
        description="Whether this source is currently scheduled for periodic refresh."
    )
    refresh_policy: RefreshPolicy = Field(
        default=RefreshPolicy.WEEKLY,
        description="Refresh cadence."
    )
    last_checked_at: datetime | None = Field(
        default=None,
        description="Timestamp of the most recent change check attempt."
    )
    last_successful_fetch_at: datetime | None = Field(
        default=None,
        description="Timestamp when content was last fetched and verified."
    )
    last_content_hash: str | None = Field(
        default=None,
        description="SHA-256 fingerprint of the latest verified content version."
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of source purpose and jurisdiction."
    )

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("source_id cannot be empty.")
        return s

    @field_validator("expected_domain")
    @classmethod
    def normalize_expected_domain(cls, v: str) -> str:
        s = v.strip().lower()
        if not s or "/" in s or ":" in s:
            raise ValueError(f"expected_domain must be a plain hostname without paths or ports: '{v}'")
        return s

    @field_validator("canonical_url")
    @classmethod
    def validate_url(cls, v: HttpUrl) -> HttpUrl:
        if v.scheme != "https":
            raise ValueError(f"All authoritative sources must use HTTPS, got scheme '{v.scheme}'.")
        if v.username or v.password:
            raise ValueError("Authoritative URLs must not contain embedded user credentials.")
        return v

    @model_validator(mode="after")
    def validate_source_invariants(self) -> "SourceRegistryEntry":
        # Organisation sources MUST have non-empty organisation_id
        if self.source_class.is_organisation:
            org_id = self.organisation_id.strip() if self.organisation_id else ""
            if not org_id:
                raise ValueError(
                    f"organisation_id is required for source '{self.source_id}' with class '{self.source_class.value}'."
                )

        # Expected domain must match or be a parent domain of canonical_url host
        url_host = self.canonical_url.host.lower() if self.canonical_url.host else ""
        exp_domain = self.expected_domain.lower()
        if not (url_host == exp_domain or url_host.endswith("." + exp_domain)):
            raise ValueError(
                f"canonical_url host '{url_host}' does not match expected_domain '{exp_domain}'."
            )

        return self


class SourceCheckResult(BaseModel):
    """Structured report of a change detection check on a registered source."""
    source_id: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: SourceCheckStatus
    previous_hash: str | None = None
    new_hash: str | None = None
    document_id: str | None = None
    version_id: str | None = None
    error_message: str | None = None
