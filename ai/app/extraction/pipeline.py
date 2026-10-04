"""Provision extraction and normalization pipeline for SANGYAN.

Coordinates:
DocumentSection
      ↓
Candidate Boundary Detection
      ↓
Structural Extraction (LLM or Deterministic)
      ↓
Pydantic Validation
      ↓
Source-Span Validation (source_text MUST be exact substring of section content)
      ↓
Metadata Inheritance (authority, organisation_id, source_class, temporal metadata)
      ↓
Cross-reference Detection
      ↓
Provision Persistence
"""

import time
from datetime import datetime, timezone
from typing import Any, Sequence
from pydantic import BaseModel, Field

from ai.app.db.repository import PostgresKnowledgeRepository
from ai.app.extraction.extractor import (
    DeterministicProvisionExtractor,
    LLMProvisionExtractor,
    ProvisionExtractor,
)
from ai.app.extraction.validator import ProvisionValidator
from ai.app.ingestion.pipeline import InMemoryKnowledgeRepository
from ai.app.knowledge.documents import DocumentSection, OrganisationDocument, RegulatoryDocument
from ai.app.knowledge.provisions import Provision, ProvisionType
from ai.app.knowledge.source_classes import SourceClass


class ExtractionMetrics(BaseModel):
    """Execution telemetry and quality metrics for provision extraction."""
    documents_processed: int = 0
    sections_processed: int = 0
    provisions_extracted: int = 0
    validation_failures: int = 0
    duplicate_provisions: int = 0
    type_distribution: dict[str, int] = Field(default_factory=dict)
    authority_breakdown: dict[str, int] = Field(default_factory=dict)
    organisation_breakdown: dict[str, int] = Field(default_factory=dict)
    source_class_breakdown: dict[str, int] = Field(default_factory=dict)
    total_conditions: int = 0
    total_exceptions: int = 0
    total_procedures: int = 0
    total_timelines: int = 0
    total_fees: int = 0
    total_definitions: int = 0
    total_cross_references: int = 0
    total_duration_sec: float = 0.0


class ProvisionExtractionPipeline:
    """End-to-end pipeline for extracting, validating, and persisting knowledge provisions."""

    def __init__(
        self,
        extractor: ProvisionExtractor | None = None,
        repository: PostgresKnowledgeRepository | InMemoryKnowledgeRepository | None = None,
    ) -> None:
        self.extractor = extractor or DeterministicProvisionExtractor()
        self.repository = repository or InMemoryKnowledgeRepository()
        self.validator = ProvisionValidator()

    async def process_section(
        self,
        section_key: str,
        section_heading: str | None,
        section_content: str,
        document_id: str,
        authority: str | None,
        organisation_id: str | None,
        source_class: SourceClass,
        canonical_url: str | None = None,
        source_hash: str | None = None,
        parent_topics: list[str] | None = None,
        effective_date: Any = None,
        termination_date: Any = None,
    ) -> list[Provision]:
        """Extract and validate provisions from a single structural section."""
        raw_provisions = await self.extractor.extract_provisions(
            section_key=section_key,
            section_heading=section_heading,
            section_content=section_content,
            document_id=document_id,
            authority=authority,
            organisation_id=organisation_id,
            source_class=source_class,
            canonical_url=canonical_url,
            source_hash=source_hash,
            parent_topics=parent_topics,
        )

        valid_provisions: list[Provision] = []
        for prov in raw_provisions:
            # Inherit dates if document has them and provision doesn't
            if effective_date and not prov.effective_date:
                prov.effective_date = effective_date
            if termination_date and not prov.termination_date:
                prov.termination_date = termination_date

            val_res = self.validator.validate_provision(
                provision=prov,
                section_content=section_content,
                expected_document_id=document_id,
                expected_section_id=section_key,
                expected_authority=authority,
                expected_organisation_id=organisation_id,
                expected_source_class=source_class,
            )

            if val_res.is_valid:
                valid_provisions.append(prov)

        return valid_provisions

    async def run_pipeline_on_sections(
        self,
        sections_data: Sequence[dict[str, Any]],
        doc_metadata_map: dict[str, dict[str, Any]],
    ) -> tuple[list[Provision], ExtractionMetrics]:
        """Execute extraction across a collection of document sections with telemetry."""
        t_start = time.perf_counter()
        metrics = ExtractionMetrics()
        all_provisions: list[Provision] = []
        seen_doc_ids: set[str] = set()
        seen_prov_ids: set[str] = set()

        for sec in sections_data:
            doc_id = sec["document_id"]
            seen_doc_ids.add(doc_id)
            metrics.sections_processed += 1

            doc_meta = doc_metadata_map.get(doc_id, {})
            auth = doc_meta.get("authority")
            org_id = doc_meta.get("organisation_id")
            s_class = doc_meta.get("source_class", SourceClass.REGULATORY)
            url = doc_meta.get("source_url")
            s_hash = doc_meta.get("source_hash")
            topics = doc_meta.get("topic", [])
            eff_date = doc_meta.get("effective_date")
            term_date = doc_meta.get("termination_date")

            extracted = await self.process_section(
                section_key=sec.get("section_key", f"sec_{sec.get('id', 0)}"),
                section_heading=sec.get("heading"),
                section_content=sec.get("content", ""),
                document_id=doc_id,
                authority=auth,
                organisation_id=org_id,
                source_class=s_class,
                canonical_url=url,
                source_hash=s_hash,
                parent_topics=topics,
                effective_date=eff_date,
                termination_date=term_date,
            )

            for p in extracted:
                if p.provision_id in seen_prov_ids:
                    metrics.duplicate_provisions += 1
                    continue
                seen_prov_ids.add(p.provision_id)

                all_provisions.append(p)
                metrics.provisions_extracted += 1

                # Telemetry breakdown
                pt_val = p.provision_type.value
                metrics.type_distribution[pt_val] = metrics.type_distribution.get(pt_val, 0) + 1

                if p.authority:
                    metrics.authority_breakdown[p.authority] = metrics.authority_breakdown.get(p.authority, 0) + 1
                if p.organisation_id:
                    metrics.organisation_breakdown[p.organisation_id] = metrics.organisation_breakdown.get(p.organisation_id, 0) + 1
                metrics.source_class_breakdown[p.source_class.value] = metrics.source_class_breakdown.get(p.source_class.value, 0) + 1

                metrics.total_conditions += len(p.conditions)
                metrics.total_exceptions += len(p.exceptions)
                metrics.total_procedures += len(p.procedures)
                metrics.total_timelines += len(p.timelines)
                metrics.total_fees += len(p.fees)
                metrics.total_definitions += len(p.definitions)
                metrics.total_cross_references += len(p.cross_references)

        metrics.documents_processed = len(seen_doc_ids)

        # Persist to repository
        if hasattr(self.repository, "save_provisions"):
            await self.repository.save_provisions(all_provisions)

        metrics.total_duration_sec = round(time.perf_counter() - t_start, 3)
        return all_provisions, metrics
