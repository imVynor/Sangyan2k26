"""SANGYAN Official Source Registry and Acquisition Module."""

from ai.app.sources.change_detector import ChangeDetector
from ai.app.sources.discovery import BoundedDiscoveryService, DiscoveredCandidate
from ai.app.sources.models import (
    DiscoveryMethod,
    RefreshPolicy,
    SourceCheckResult,
    SourceCheckStatus,
    SourceRegistryEntry,
    SourceStatus,
)
from ai.app.sources.registry import DEFAULT_OFFICIAL_SOURCES, SourceRegistry
from ai.app.sources.scheduler import SourceScheduler
from ai.app.sources.validators import (
    SourceSecurityError,
    is_subdomain_of,
    validate_content_type,
    validate_source_url,
)

__all__ = [
    "SourceRegistryEntry",
    "SourceCheckResult",
    "SourceCheckStatus",
    "RefreshPolicy",
    "DiscoveryMethod",
    "SourceStatus",
    "SourceRegistry",
    "DEFAULT_OFFICIAL_SOURCES",
    "BoundedDiscoveryService",
    "DiscoveredCandidate",
    "ChangeDetector",
    "SourceScheduler",
    "SourceSecurityError",
    "is_subdomain_of",
    "validate_source_url",
    "validate_content_type",
]
