"""Structured exception hierarchy for the SANGYAN ingestion pipeline.

Every failure explicitly identifies the ingestion stage:
FETCH, CLASSIFICATION, EXTRACTION, NORMALIZATION, VALIDATION, DEDUPLICATION.
"""

from enum import Enum


class IngestionStage(str, Enum):
    """Lifecycle stages of deterministic ingestion."""
    FETCH = "FETCH"
    CLASSIFICATION = "CLASSIFICATION"
    EXTRACTION = "EXTRACTION"
    NORMALIZATION = "NORMALIZATION"
    VALIDATION = "VALIDATION"
    DEDUPLICATION = "DEDUPLICATION"


class IngestionError(Exception):
    """Base exception for all ingestion pipeline failures."""

    def __init__(self, stage: IngestionStage, message: str, details: dict | None = None):
        super().__init__(f"[{stage.value}] {message}")
        self.stage = stage
        self.message = message
        self.details = details or {}


class FetchError(IngestionError):
    """Raised when HTTP request fails, times out, or exceeds size limits."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(IngestionStage.FETCH, message, details)


class DomainValidationError(IngestionError):
    """Raised when URL or redirect destination violates domain constraints."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(IngestionStage.FETCH, message, details)


class ClassificationError(IngestionError):
    """Raised when document content-type is unsupported."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(IngestionStage.CLASSIFICATION, message, details)


class ExtractionError(IngestionError):
    """Raised when HTML or PDF extraction yields no extractable content or fails."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(IngestionStage.EXTRACTION, message, details)


class NormalizationError(IngestionError):
    """Raised when extracted content cannot be mapped into valid canonical contracts."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(IngestionStage.NORMALIZATION, message, details)


class ValidationError(IngestionError):
    """Raised when canonical schemas reject ingested structures."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(IngestionStage.VALIDATION, message, details)


class DuplicateContentError(IngestionError):
    """Raised when identical content hash has already been ingested."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(IngestionStage.DEDUPLICATION, message, details)
