"""Ingestion package for SANGYAN knowledge pipeline."""

from ai.app.ingestion.classifier import DocumentFormat, classify_document
from ai.app.ingestion.errors import (
    ClassificationError,
    DomainValidationError,
    DuplicateContentError,
    ExtractionError,
    FetchError,
    IngestionError,
    IngestionStage,
    NormalizationError,
    ValidationError,
)
from ai.app.ingestion.fetcher import DocumentFetcher, is_domain_allowed
from ai.app.ingestion.fingerprint import compute_source_hash, generate_deterministic_document_id
from ai.app.ingestion.html_extractor import extract_html
from ai.app.ingestion.models import (
    ExtractedContent,
    FetchedPayload,
    IngestionRequest,
    IngestionResult,
    IngestionStatus,
)
from ai.app.ingestion.normalizer import normalize_ingested_content
from ai.app.ingestion.pdf_extractor import extract_pdf
from ai.app.ingestion.pipeline import InMemoryKnowledgeRepository, IngestionPipeline

__all__ = [
    "IngestionStage",
    "IngestionStatus",
    "IngestionError",
    "FetchError",
    "DomainValidationError",
    "ClassificationError",
    "ExtractionError",
    "NormalizationError",
    "ValidationError",
    "DuplicateContentError",
    "IngestionRequest",
    "FetchedPayload",
    "ExtractedContent",
    "IngestionResult",
    "DocumentFormat",
    "classify_document",
    "compute_source_hash",
    "generate_deterministic_document_id",
    "DocumentFetcher",
    "is_domain_allowed",
    "extract_html",
    "extract_pdf",
    "normalize_ingested_content",
    "InMemoryKnowledgeRepository",
    "IngestionPipeline",
]
