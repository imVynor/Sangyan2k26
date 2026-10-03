"""Deterministic knowledge ingestion pipeline for SANGYAN.

Architecture:
FETCH → IDENTIFY → EXTRACT → NORMALIZE → CLASSIFY → FINGERPRINT → VALIDATE

Strictly non-interpretive:
- Zero LLM summarization or inference.
- Zero shell commands or arbitrary script execution.
- Deterministic deduplication by SHA-256 content hash.
- Identifies exact failure stages in machine-readable errors.
"""

from typing import Any
from ai.app.ingestion.classifier import DocumentFormat, classify_document
from ai.app.ingestion.errors import (
    ClassificationError,
    DomainValidationError,
    ExtractionError,
    FetchError,
    IngestionStage,
)
from ai.app.ingestion.fetcher import DocumentFetcher
from ai.app.ingestion.fingerprint import compute_source_hash
from ai.app.ingestion.html_extractor import extract_html
from ai.app.ingestion.models import IngestionRequest, IngestionResult, IngestionStatus
from ai.app.ingestion.normalizer import normalize_ingested_content
from ai.app.ingestion.pdf_extractor import extract_pdf
from ai.app.knowledge.documents import (
    NormalizedDocument,
    OrganisationDocument,
    RegulatoryDocument,
)
from ai.app.organisation.contracts import OrganisationKnowledgeRepository
from ai.app.regulatory.contracts import RegulatoryKnowledgeRepository
from ai.app.utils.logging import log_llm_event


class InMemoryKnowledgeRepository(RegulatoryKnowledgeRepository, OrganisationKnowledgeRepository):
    """In-memory store for development, testing, and deduplication verification.
    
    Implements Phase 1A repository contracts without external database dependencies.
    """

    def __init__(self) -> None:
        self._normalized_docs: dict[str, NormalizedDocument] = {}
        self._regulatory_docs: dict[str, RegulatoryDocument] = {}
        self._organisation_docs: dict[str, OrganisationDocument] = {}
        self._hash_to_doc_id: dict[str, str] = {}
        self._knowledge_provisions: dict[str, Any] = {}

    def has_hash(self, source_hash: str) -> bool:
        """Check if identical content hash has already been stored."""
        return source_hash in self._hash_to_doc_id

    def get_by_hash(self, source_hash: str) -> NormalizedDocument | None:
        doc_id = self._hash_to_doc_id.get(source_hash)
        if doc_id:
            return self._normalized_docs.get(doc_id)
        return None

    async def get_document(self, document_id: str) -> RegulatoryDocument | None:
        return self._regulatory_docs.get(document_id)

    async def get_provision(self, provision_id: str) -> Any:
        return self._knowledge_provisions.get(provision_id)

    async def get_knowledge_provision(self, provision_id: str) -> Any:
        return self._knowledge_provisions.get(provision_id)

    async def list_provisions_for_document(self, document_id: str) -> list:
        return [p for p in self._knowledge_provisions.values() if getattr(p, "document_id", None) == document_id]

    async def list_provisions_by_document(self, document_id: str) -> list:
        return [p for p in self._knowledge_provisions.values() if getattr(p, "document_id", None) == document_id]

    async def list_all_knowledge_provisions(self) -> list:
        return list(self._knowledge_provisions.values())

    async def save_provisions(self, provisions: list) -> int:
        count = 0
        for p in provisions:
            pid = getattr(p, "provision_id", None)
            if pid and pid not in self._knowledge_provisions:
                self._knowledge_provisions[pid] = p
                count += 1
        return count

    async def list_documents_for_org(self, organisation_id: str) -> list[OrganisationDocument]:
        return [
            doc for doc in self._organisation_docs.values()
            if doc.organisation_id == organisation_id
        ]

    def save(
        self,
        normalized_doc: NormalizedDocument,
        reg_doc: RegulatoryDocument | None = None,
        org_doc: OrganisationDocument | None = None,
    ) -> None:
        """Commit document to in-memory store."""
        doc_id = normalized_doc.document_id
        self._normalized_docs[doc_id] = normalized_doc
        self._hash_to_doc_id[normalized_doc.source_hash] = doc_id
        if reg_doc:
            self._regulatory_docs[doc_id] = reg_doc
        if org_doc:
            self._organisation_docs[doc_id] = org_doc


class IngestionPipeline:
    """Deterministic orchestrator for document fetching, extraction, normalization, and deduplication."""

    def __init__(
        self,
        fetcher: DocumentFetcher | None = None,
        repository: InMemoryKnowledgeRepository | None = None,
    ) -> None:
        self.fetcher = fetcher or DocumentFetcher()
        self.repository = repository or InMemoryKnowledgeRepository()

    async def ingest(self, request: IngestionRequest) -> IngestionResult:
        """Execute the deterministic ingestion pipeline."""
        source_url_str = str(request.source_url)
        log_llm_event(
            event="ingestion_start",
            model="deterministic_pipeline",
            extra={"source_url": source_url_str, "source_class": request.source_class.value},
        )

        # -------------------------------------------------------------
        # 1. FETCH STAGE
        # -------------------------------------------------------------
        try:
            payload = await self.fetcher.fetch(
                url=request.source_url,
                expected_domain=request.expected_domain,
            )
        except DomainValidationError as exc:
            return IngestionResult(
                success=False,
                status=IngestionStatus.DOMAIN_VALIDATION_FAILED,
                stage=IngestionStage.FETCH,
                errors=[str(exc)],
            )
        except FetchError as exc:
            return IngestionResult(
                success=False,
                status=IngestionStatus.FETCH_FAILED,
                stage=IngestionStage.FETCH,
                errors=[str(exc)],
            )
        except Exception as exc:
            return IngestionResult(
                success=False,
                status=IngestionStatus.FETCH_FAILED,
                stage=IngestionStage.FETCH,
                errors=[f"Unexpected transport failure: {exc}"],
            )

        # -------------------------------------------------------------
        # 2. FINGERPRINT & DEDUPLICATION STAGE
        # -------------------------------------------------------------
        source_hash = compute_source_hash(payload.raw_bytes)

        if not request.force_reingest and self.repository.has_hash(source_hash):
            existing_doc = self.repository.get_by_hash(source_hash)
            existing_doc_id = existing_doc.document_id if existing_doc else None
            return IngestionResult(
                success=True,
                status=IngestionStatus.DUPLICATE_CONTENT,
                stage=IngestionStage.DEDUPLICATION,
                document_id=existing_doc_id,
                source_hash=source_hash,
                final_url=payload.final_url,
                normalized_document=existing_doc,
                warnings=["Identical content hash already ingested. Returning existing document."],
            )

        # -------------------------------------------------------------
        # 3. CLASSIFICATION STAGE
        # -------------------------------------------------------------
        doc_format = classify_document(
            content_type=payload.content_type,
            raw_bytes=payload.raw_bytes,
            url=str(payload.final_url),
        )

        if doc_format == DocumentFormat.UNSUPPORTED:
            return IngestionResult(
                success=False,
                status=IngestionStatus.UNSUPPORTED_CONTENT,
                stage=IngestionStage.CLASSIFICATION,
                source_hash=source_hash,
                final_url=payload.final_url,
                errors=[f"Unsupported document format with Content-Type: '{payload.content_type}'"],
            )

        # -------------------------------------------------------------
        # 4. EXTRACTION STAGE
        # -------------------------------------------------------------
        try:
            if doc_format == DocumentFormat.HTML:
                extracted = extract_html(payload.raw_bytes)
            elif doc_format == DocumentFormat.PDF:
                extracted = extract_pdf(payload.raw_bytes)
            else:
                raise ClassificationError(f"Unexpected format: {doc_format}")
        except ExtractionError as exc:
            return IngestionResult(
                success=False,
                status=IngestionStatus.EXTRACTION_FAILED,
                stage=IngestionStage.EXTRACTION,
                source_hash=source_hash,
                final_url=payload.final_url,
                errors=[str(exc)],
            )
        except Exception as exc:
            return IngestionResult(
                success=False,
                status=IngestionStatus.EXTRACTION_FAILED,
                stage=IngestionStage.EXTRACTION,
                source_hash=source_hash,
                final_url=payload.final_url,
                errors=[f"Extraction error: {exc}"],
            )

        # -------------------------------------------------------------
        # 5. NORMALIZATION STAGE
        # -------------------------------------------------------------
        try:
            norm_doc, reg_doc, org_doc = normalize_ingested_content(
                request=request,
                payload=payload,
                extracted=extracted,
                source_hash=source_hash,
            )
        except Exception as exc:
            return IngestionResult(
                success=False,
                status=IngestionStatus.VALIDATION_FAILED,
                stage=IngestionStage.NORMALIZATION,
                source_hash=source_hash,
                final_url=payload.final_url,
                errors=[f"Normalization error: {exc}"],
            )

        # -------------------------------------------------------------
        # 6. STORAGE & COMPLETION
        # -------------------------------------------------------------
        self.repository.save(
            normalized_doc=norm_doc,
            reg_doc=reg_doc,
            org_doc=org_doc,
        )

        log_llm_event(
            event="ingestion_success",
            model="deterministic_pipeline",
            extra={
                "document_id": norm_doc.document_id,
                "source_hash": source_hash,
                "sections_count": len(norm_doc.sections),
            },
        )

        return IngestionResult(
            success=True,
            status=IngestionStatus.SUCCESS,
            stage=IngestionStage.VALIDATION,
            document_id=norm_doc.document_id,
            source_hash=source_hash,
            document_type=request.document_type,
            final_url=payload.final_url,
            normalized_document=norm_doc,
            regulatory_document=reg_doc,
            organisation_document=org_doc,
        )
