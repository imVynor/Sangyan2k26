"""Controlled corpus ingestion runner for SANGYAN.

Processes an explicit CorpusManifest by mapping entries to IngestionRequest specifications,
invoking the existing Phase 1B deterministic ingestion pipeline, persisting through the
Phase 1C-A knowledge repository, and generating structured execution summaries.

Strict boundaries:
- NO automatic link crawling or spidering.
- NO search engine discovery.
- Exactly the explicit sources defined in the manifest are processed.
- Dry run executes 0 network calls and 0 database writes.
- Deduplication is guaranteed through Phase 1B hash fingerprints + Phase 1C-A persistence.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to sys.path if running as script
ai_root = Path(__file__).resolve().parent.parent.parent
project_root = ai_root.parent
for p in [str(ai_root), str(project_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    import asyncio

from ai.app.corpus.models import (
    CorpusManifest,
    CorpusRunResult,
    SourceExecutionStatus,
    SourceRunResult,
)
from ai.app.corpus.validator import CorpusValidationError, validate_manifest
from ai.app.db.repository import PostgresKnowledgeRepository
from ai.app.ingestion.models import IngestionRequest, IngestionStatus
from ai.app.ingestion.pipeline import IngestionPipeline


class CorpusRunner:
    """Orchestrates controlled acquisition for an explicit corpus manifest."""

    def __init__(
        self,
        pipeline: IngestionPipeline | None = None,
        pg_repo: PostgresKnowledgeRepository | None = None,
    ) -> None:
        self.pipeline = pipeline or IngestionPipeline()
        self.pg_repo = pg_repo

    async def run(self, manifest: CorpusManifest, dry_run: bool = False) -> CorpusRunResult:
        """Execute acquisition for all explicit entries in the given manifest.
        
        Args:
            manifest: Validated CorpusManifest containing explicit source specifications.
            dry_run: If True, validates manifest and plans execution without performing
                     HTTP requests or database mutations.
                     
        Returns:
            CorpusRunResult detailing outcomes for all sources.
        """
        # Validate manifest invariants
        validate_manifest(manifest)
        started_at = datetime.now(timezone.utc)
        results: list[SourceRunResult] = []

        if dry_run:
            print("\n[DRY RUN MODE] Manifest validated. Planning source acquisition:")
            for idx, source in enumerate(manifest.sources, 1):
                org_info = f" (org: {source.organisation_id})" if source.organisation_id else ""
                auth_info = f" (auth: {source.authority})" if source.authority else ""
                print(f"  {idx}. [{source.source_class.value}] {source.source_id}{org_info}{auth_info} -> {source.url}")
                results.append(
                    SourceRunResult(
                        source_id=source.source_id,
                        url=str(source.url),
                        status=SourceExecutionStatus.DRY_RUN.value,
                    )
                )

            completed_at = datetime.now(timezone.utc)
            return CorpusRunResult(
                corpus_version=manifest.corpus_version,
                started_at=started_at,
                completed_at=completed_at,
                total_sources=len(manifest.sources),
                successful_sources=0,
                duplicate_sources=0,
                failed_sources=0,
                results=results,
            )

        # LIVE EXECUTION: Strictly process only explicitly listed sources
        for source in manifest.sources:
            request = IngestionRequest(
                source_url=source.url,
                expected_domain=source.expected_domain,
                source_class=source.source_class,
                organisation_id=source.organisation_id,
                authority=source.authority,
                document_type=source.document_type,
                force_reingest=False,
            )

            try:
                ingest_res = await self.pipeline.ingest(request)
            except Exception as exc:
                err_msg = f"Unexpected pipeline execution error: {exc}"
                results.append(
                    SourceRunResult(
                        source_id=source.source_id,
                        url=str(source.url),
                        status=SourceExecutionStatus.FAILED.value,
                        error_stage="PIPELINE",
                        error_message=err_msg,
                    )
                )
                if self.pg_repo:
                    await self._record_attempt(
                        source=source,
                        status=SourceExecutionStatus.FAILED.value,
                        source_hash="",
                        document_id=None,
                        final_url=str(source.url),
                        error_stage="PIPELINE",
                        error_message=err_msg,
                    )
                continue

            # Determine outcome and persist
            if ingest_res.status == IngestionStatus.DUPLICATE_CONTENT:
                status = SourceExecutionStatus.DUPLICATE.value
                doc_id = ingest_res.document_id
                s_hash = ingest_res.source_hash
                err_stage = None
                err_msg = None
                if self.pg_repo:
                    await self._record_attempt(
                        source=source,
                        status=status,
                        source_hash=s_hash or "",
                        document_id=doc_id,
                        final_url=str(ingest_res.final_url) if ingest_res.final_url else str(source.url),
                    )

            elif ingest_res.success:
                s_hash = ingest_res.source_hash or ""
                doc_id = ingest_res.document_id
                err_stage = None
                err_msg = None

                if self.pg_repo:
                    # Check if hash already exists in PostgreSQL persistence
                    if await self.pg_repo.has_hash(s_hash):
                        status = SourceExecutionStatus.DUPLICATE.value
                    else:
                        await self.pg_repo.save_ingested_knowledge(
                            normalized_doc=ingest_res.normalized_document,  # type: ignore
                            reg_doc=ingest_res.regulatory_document,
                            org_doc=ingest_res.organisation_document,
                        )
                        status = SourceExecutionStatus.SUCCESS.value

                    await self._record_attempt(
                        source=source,
                        status=status,
                        source_hash=s_hash,
                        document_id=doc_id,
                        final_url=str(ingest_res.final_url) if ingest_res.final_url else str(source.url),
                    )
                else:
                    status = SourceExecutionStatus.SUCCESS.value

            else:
                # Failed ingestion
                status = SourceExecutionStatus.FAILED.value
                doc_id = None
                s_hash = ingest_res.source_hash
                err_stage = ingest_res.stage.value if ingest_res.stage else None
                err_msg = "; ".join(ingest_res.errors) if ingest_res.errors else "Ingestion failed"

                if self.pg_repo:
                    await self._record_attempt(
                        source=source,
                        status=status,
                        source_hash=s_hash or "",
                        document_id=None,
                        final_url=str(ingest_res.final_url) if ingest_res.final_url else str(source.url),
                        error_stage=err_stage,
                        error_message=err_msg,
                    )

            results.append(
                SourceRunResult(
                    source_id=source.source_id,
                    url=str(source.url),
                    status=status,
                    document_id=doc_id,
                    source_hash=s_hash,
                    error_stage=err_stage,
                    error_message=err_msg,
                )
            )

        completed_at = datetime.now(timezone.utc)
        return CorpusRunResult(
            corpus_version=manifest.corpus_version,
            started_at=started_at,
            completed_at=completed_at,
            total_sources=len(results),
            successful_sources=sum(1 for r in results if r.status == SourceExecutionStatus.SUCCESS.value),
            duplicate_sources=sum(1 for r in results if r.status == SourceExecutionStatus.DUPLICATE.value),
            failed_sources=sum(1 for r in results if r.status == SourceExecutionStatus.FAILED.value),
            results=results,
        )

    async def _record_attempt(
        self,
        source: Any,
        status: str,
        source_hash: str,
        document_id: str | None,
        final_url: str,
        error_stage: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Helper to write ingestion audit records to PostgreSQL."""
        if not self.pg_repo:
            return
        try:
            ingestion_id = f"INGEST-{source.source_id}-{int(datetime.now(timezone.utc).timestamp())}"
            await self.pg_repo.record_ingestion_attempt(
                ingestion_id=ingestion_id,
                source_url=str(source.url),
                final_url=final_url,
                source_hash=source_hash,
                document_id=document_id,
                ingestion_status=status,
                retrieved_at=datetime.now(timezone.utc),
                error_stage=error_stage,
                error_message=error_message,
            )
        except Exception as exc:
            print(f"[WARNING] Failed to write ingestion audit record for {source.source_id}: {exc}")


def print_run_summary(run_result: CorpusRunResult) -> None:
    """Format and print structured execution report to standard output."""
    duration = (run_result.completed_at - run_result.started_at).total_seconds()
    print("\n" + "=" * 65)
    print("SANGYAN Corpus Acquisition Report")
    print("=" * 65)
    print(f"Corpus Version:     {run_result.corpus_version}")
    print(f"Execution Duration: {duration:.2f}s")
    print(f"Total Sources:      {run_result.total_sources}")
    print(f"  - Successful:     {run_result.successful_sources}")
    print(f"  - Duplicate:      {run_result.duplicate_sources}")
    print(f"  - Failed:         {run_result.failed_sources}")
    print("-" * 65)
    for res in run_result.results:
        status_tag = f"[{res.status}]".ljust(12)
        doc_part = f"doc: {res.document_id}" if res.document_id else ""
        err_part = f"({res.error_stage}: {res.error_message})" if res.error_message else ""
        detail = doc_part or err_part or ""
        print(f"  {status_tag} {res.source_id} -> {detail}")
    print("=" * 65)


async def main_cli() -> int:
    """CLI entrypoint for running corpus manifests."""
    parser = argparse.ArgumentParser(
        description="SANGYAN Reproducible Corpus Manifest Acquisition Runner"
    )
    parser.add_argument(
        "--manifest",
        "-m",
        required=True,
        help="Path to the corpus manifest YAML file (e.g. ai/corpus/manifest.example.yaml).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manifest and print planned sources without network or database activity.",
    )
    parser.add_argument(
        "--use-db",
        action="store_true",
        help="Persist ingested knowledge into PostgreSQL (requires DATABASE_URL).",
    )

    args = parser.parse_args()

    from ai.app.corpus.loader import load_manifest

    try:
        manifest = load_manifest(args.manifest)
    except (FileNotFoundError, CorpusValidationError) as exc:
        print(f"\n[ERROR] Failed to load manifest: {exc}", file=sys.stderr)
        return 1

    pg_repo = None
    if args.use_db and not args.dry_run:
        from ai.app.config.settings import settings
        db_url = settings.database_url or os.environ.get("DATABASE_URL")
        if not db_url:
            print("\n[ERROR] --use-db specified but DATABASE_URL is not set.", file=sys.stderr)
            return 1
        pg_repo = PostgresKnowledgeRepository()

    runner = CorpusRunner(pg_repo=pg_repo)
    result = await runner.run(manifest, dry_run=args.dry_run)
    print_run_summary(result)

    return 0 if result.failed_sources == 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main_cli()))
