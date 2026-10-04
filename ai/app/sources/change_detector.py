"""Change detection and continuous knowledge refresh service for SANGYAN.

Guarantees:
- Every registered source is periodically checked for content modifications.
- Unchanged sources do NOT create duplicate documents.
- Changed sources produce new document versions while preserving historical versions immutably.
- Provenance and SHA-256 fingerprints are strictly tracked.
- Disappearing/failing sources are flagged as UNAVAILABLE without losing historical data.
"""

from datetime import datetime, timezone
from typing import Any

from ai.app.ingestion.errors import DomainValidationError, FetchError
from ai.app.ingestion.fetcher import DocumentFetcher
from ai.app.ingestion.fingerprint import compute_source_hash
from ai.app.ingestion.models import IngestionRequest, IngestionStatus
from ai.app.ingestion.pipeline import InMemoryKnowledgeRepository, IngestionPipeline
from ai.app.knowledge.relationships import KnowledgeRelationship, RelationshipType
from ai.app.sources.models import (
    SourceCheckResult,
    SourceCheckStatus,
    SourceRegistryEntry,
)
from ai.app.sources.registry import SourceRegistry


class ChangeDetector:
    """Evaluates registered sources against their latest known fingerprints."""

    def __init__(
        self,
        fetcher: DocumentFetcher | None = None,
        pipeline: IngestionPipeline | None = None,
        registry: SourceRegistry | None = None,
    ) -> None:
        self.fetcher = fetcher or DocumentFetcher()
        self.pipeline = pipeline or IngestionPipeline(fetcher=self.fetcher)
        self.registry = registry or SourceRegistry()

    async def check_source(self, entry: SourceRegistryEntry) -> SourceCheckResult:
        """Execute change detection on a single registered source."""
        now = datetime.now(timezone.utc)

        # 1. Fetch content with domain validation
        try:
            payload = await self.fetcher.fetch(
                url=entry.canonical_url,
                expected_domain=entry.expected_domain,
            )
        except DomainValidationError as exc:
            return SourceCheckResult(
                source_id=entry.source_id,
                checked_at=now,
                status=SourceCheckStatus.MALICIOUS_REDIRECT,
                error_message=f"Malicious or illegal redirect: {exc}",
            )
        except FetchError as exc:
            return SourceCheckResult(
                source_id=entry.source_id,
                checked_at=now,
                status=SourceCheckStatus.UNAVAILABLE,
                error_message=f"Source unavailable: {exc}",
            )
        except Exception as exc:
            return SourceCheckResult(
                source_id=entry.source_id,
                checked_at=now,
                status=SourceCheckStatus.FETCH_FAILED,
                error_message=f"Transport error: {exc}",
            )

        # 2. Compute SHA-256 fingerprint
        current_hash = compute_source_hash(payload.raw_bytes)

        # 3. Compare with latest known content hash
        if entry.last_content_hash is not None and entry.last_content_hash == current_hash:
            # UNCHANGED: Mark source checked, do NOT duplicate
            self.registry.update_check_record(
                source_id=entry.source_id,
                checked_at=now,
                content_hash=current_hash,
                success=True,
            )
            return SourceCheckResult(
                source_id=entry.source_id,
                checked_at=now,
                status=SourceCheckStatus.UNCHANGED,
                previous_hash=entry.last_content_hash,
                new_hash=current_hash,
            )

        # 4. Content has changed or is new: Ingest through deterministic pipeline
        is_first_version = entry.last_content_hash is None
        request = IngestionRequest(
            source_url=entry.canonical_url,
            expected_domain=entry.expected_domain,
            source_class=entry.source_class,
            organisation_id=entry.organisation_id,
            authority=entry.authority,
            document_type=entry.document_type,
            force_reingest=True,  # Bypass deduplication since we verified content changed
        )

        ingest_res = await self.pipeline.ingest(request)
        if not ingest_res.success:
            return SourceCheckResult(
                source_id=entry.source_id,
                checked_at=now,
                status=SourceCheckStatus.FETCH_FAILED,
                previous_hash=entry.last_content_hash,
                new_hash=current_hash,
                error_message="; ".join(ingest_res.errors) or "Ingestion pipeline failure",
            )

        prev_hash = entry.last_content_hash
        self.registry.update_check_record(
            source_id=entry.source_id,
            checked_at=now,
            content_hash=current_hash,
            success=True,
        )

        status = SourceCheckStatus.NEW_DOCUMENT if is_first_version else SourceCheckStatus.CHANGED
        return SourceCheckResult(
            source_id=entry.source_id,
            checked_at=now,
            status=status,
            previous_hash=prev_hash,
            new_hash=current_hash,
            document_id=ingest_res.document_id,
        )
