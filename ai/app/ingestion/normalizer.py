"""Deterministic normalization into canonical SANGYAN document contracts.

Enforces:
- Document status defaults strictly to UNKNOWN (download != legally current).
- Dates and identifiers are never invented: missing metadata remains None.
- Provenance is fully preserved with deterministic document IDs and source hash.
- Hierarchical sections are maintained.
"""

from typing import Any
from ai.app.ingestion.fingerprint import generate_deterministic_document_id
from ai.app.ingestion.models import ExtractedContent, FetchedPayload, IngestionRequest
from ai.app.knowledge.documents import (
    NormalizedDocument,
    OrganisationDocument,
    RegulatoryDocument,
)
from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.temporal import SupersededStatus


def normalize_ingested_content(
    request: IngestionRequest,
    payload: FetchedPayload,
    extracted: ExtractedContent,
    source_hash: str,
) -> tuple[NormalizedDocument, RegulatoryDocument | None, OrganisationDocument | None]:
    """Convert extracted content into canonical NormalizedDocument and domain models.
    
    Returns:
        tuple of (NormalizedDocument, RegulatoryDocument or None, OrganisationDocument or None)
    """
    # 1. Deterministic document ID strategy
    document_id = generate_deterministic_document_id(
        source_class=request.source_class,
        source_hash=source_hash,
        authority=request.authority,
        organisation_id=request.organisation_id,
    )

    # 2. Build full metadata dictionary
    meta: dict[str, Any] = {
        "source_url": str(payload.final_url),
        "source_class": request.source_class.value,
        "title": extracted.title,
        "page_count": extracted.page_count,
        "content_length": payload.content_length,
        "http_status": payload.http_status,
        "content_type": payload.content_type,
        "retrieved_at": payload.retrieval_timestamp.isoformat(),
        "extractor_meta": extracted.metadata,
    }
    if request.authority:
        meta["authority"] = request.authority
    if request.organisation_id:
        meta["organisation_id"] = request.organisation_id

    # 3. Create NormalizedDocument
    normalized_doc = NormalizedDocument(
        document_id=document_id,
        metadata=meta,
        content=extracted.raw_text,
        sections=extracted.sections,
        provisions=[],
        source_hash=source_hash,
    )

    # 4. Construct domain-specific canonical document
    reg_doc: RegulatoryDocument | None = None
    org_doc: OrganisationDocument | None = None

    title = extracted.title or (
        f"{request.authority or 'Regulatory'} Document {source_hash[:8]}"
        if request.source_class.is_regulatory
        else f"{request.organisation_id or 'Organisation'} Policy {source_hash[:8]}"
    )
    doc_identifier = document_id

    if request.source_class.is_regulatory:
        reg_doc = RegulatoryDocument(
            document_id=document_id,
            authority=request.authority or "REGULATORY_AUTHORITY",
            jurisdiction="India",
            document_type=request.document_type or "Circular",
            title=title,
            document_identifier=doc_identifier,
            publication_date=None,  # Never invent dates
            effective_date=None,    # Never infer legal effective date
            termination_date=None,
            superseded_status=SupersededStatus.UNKNOWN,  # Default UNKNOWN
            source_url=payload.final_url,
            source_hash=source_hash,
            retrieved_at=payload.retrieval_timestamp,
            source_class=request.source_class,
        )
    elif request.source_class.is_organisation:
        org_doc = OrganisationDocument(
            document_id=document_id,
            organisation_id=request.organisation_id or "UNKNOWN_ORG",
            source_class=request.source_class,
            document_type=request.document_type or "Policy",
            title=title,
            document_identifier=doc_identifier,
            publication_date=None,  # Never invent dates
            effective_date=None,
            termination_date=None,
            source_url=payload.final_url,
            source_hash=source_hash,
            retrieved_at=payload.retrieval_timestamp,
            superseded_status=SupersededStatus.UNKNOWN,  # Default UNKNOWN
            organisation_name=None,
            applicable_process=None,
            topic=None,
        )

    return normalized_doc, reg_doc, org_doc
