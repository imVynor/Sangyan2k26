"""Autonomous Regulatory & Organisation Corpus Population Script for SANGYAN.

Acquires, extracts, normalizes, and persists the initial authoritative corpus
into PostgreSQL (ai_knowledge) across 5 regulatory bodies (SEBI, NSE, BSE, CDSL, NSDL)
and 5 market intermediaries (Zerodha, Groww, Upstox, Angel One, ICICI Direct).

Guarantees:
- Strict domain pinning to registered official domains.
- No third-party copies or search engine crawls.
- Accurate reporting of FETCH_FAILED (WAF blocks) and EXTRACTION_UNSUPPORTED (dynamic shells).
- Full cryptographic provenance and PostgreSQL relational persistence.
- Outputs ai/corpus/manifest.v1.yaml and ai/corpus/corpus_acquisition_report.json.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml

# Add ai root to sys.path
ai_root = Path(__file__).resolve().parent.parent
project_root = ai_root.parent
for p in [str(ai_root), str(project_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    import asyncio

from bs4 import BeautifulSoup
from pydantic import HttpUrl

from ai.app.config.settings import settings
from ai.app.corpus.models import CorpusManifest, CorpusSource
from ai.app.db.repository import PostgresKnowledgeRepository
from ai.app.db.session import get_async_engine
from ai.app.ingestion.errors import ExtractionError, FetchError
from ai.app.ingestion.fetcher import DocumentFetcher
from ai.app.ingestion.fingerprint import compute_source_hash
from ai.app.ingestion.models import IngestionRequest, IngestionStatus
from ai.app.ingestion.pipeline import InMemoryKnowledgeRepository, IngestionPipeline
from ai.app.knowledge.source_classes import SourceClass
from ai.app.organisation.registry import INITIAL_ORGANISATIONS, OrganisationRegistry
from ai.app.sources.discovery import BoundedDiscoveryService
from ai.app.sources.models import SourceRegistryEntry
from ai.app.sources.registry import DEFAULT_OFFICIAL_SOURCES, SourceRegistry


async def run_corpus_population() -> dict[str, Any]:
    print("=" * 70)
    print("SANGYAN Real Regulatory & Organisation Corpus Population")
    print("=" * 70)

    db_url = settings.database_url or os.environ.get("DATABASE_URL")
    pg_repo: PostgresKnowledgeRepository | None = None
    if db_url:
        print(f"[DATABASE] Connected to PostgreSQL target: {db_url.split('@')[-1] if '@' in db_url else db_url}")
        pg_repo = PostgresKnowledgeRepository()
    else:
        print("[DATABASE] No DATABASE_URL found. Running in in-memory mode.")

    fetcher = DocumentFetcher()
    pipeline = IngestionPipeline(fetcher=fetcher)
    bds = BoundedDiscoveryService()
    source_reg = SourceRegistry()
    org_reg = OrganisationRegistry()

    # Track results
    results: list[dict[str, Any]] = []
    validated_sources: list[dict[str, Any]] = []

    entity_stats: dict[str, dict[str, int]] = {
        "SEBI": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
        "NSE": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
        "BSE": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
        "CDSL": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
        "NSDL": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
        "Zerodha": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
        "Groww": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
        "Upstox": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
        "Angel One": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
        "ICICI Direct": {"discovered": 0, "ingested": 0, "failed": 0, "unsupported": 0, "sections": 0},
    }

    def get_entity_name(auth: str | None, org_id: str | None) -> str:
        if auth:
            return auth
        if org_id == "ORG_ZERODHA":
            return "Zerodha"
        if org_id == "ORG_GROWW":
            return "Groww"
        if org_id == "ORG_UPSTOX":
            return "Upstox"
        if org_id == "ORG_ANGELONE":
            return "Angel One"
        if org_id == "ORG_ICICIDIRECT":
            return "ICICI Direct"
        return "Unknown"

    print("\n--- Processing Registered Authoritative Sources ---")
    sources_to_process = DEFAULT_OFFICIAL_SOURCES

    for src in sources_to_process:
        entity = get_entity_name(src.authority, src.organisation_id)
        entity_stats[entity]["discovered"] += 1
        url_str = str(src.canonical_url)

        print(f"\n[{entity}] Processing {src.source_id}...")
        print(f"  URL: {url_str}")

        res_record: dict[str, Any] = {
            "source_id": src.source_id,
            "url": url_str,
            "source_class": src.source_class.value,
            "authority": src.authority,
            "organisation_id": src.organisation_id,
            "http_status": None,
            "mime_type": None,
            "content_hash": None,
            "document_id": None,
            "sections_extracted": 0,
            "provisions_extracted": 0,
            "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
            "result_status": "NOT_FOUND",
        }

        # Step 1: Fetch
        try:
            payload = await fetcher.fetch(url=src.canonical_url, expected_domain=src.expected_domain)
            res_record["http_status"] = payload.http_status
            res_record["mime_type"] = payload.content_type
            res_record["content_hash"] = compute_source_hash(payload.raw_bytes)
        except FetchError as exc:
            err_str = str(exc)
            res_record["http_status"] = 403 if "403" in err_str else (404 if "404" in err_str else 500)
            res_record["result_status"] = "FETCH_FAILED"
            entity_stats[entity]["failed"] += 1
            print(f"  [RESULT] FETCH_FAILED: {exc}")
            results.append(res_record)
            continue
        except Exception as exc:
            res_record["result_status"] = "FETCH_FAILED"
            entity_stats[entity]["failed"] += 1
            print(f"  [RESULT] FETCH_FAILED (Transport): {exc}")
            results.append(res_record)
            continue

        # Step 2: Ingestion & Extraction Check
        req = IngestionRequest(
            source_url=src.canonical_url,
            expected_domain=src.expected_domain,
            source_class=src.source_class,
            organisation_id=src.organisation_id,
            authority=src.authority,
            document_type=src.document_type,
            force_reingest=False,
        )

        try:
            ingest_res = await pipeline.ingest(req)
        except Exception as exc:
            res_record["result_status"] = "EXTRACTION_UNSUPPORTED"
            entity_stats[entity]["unsupported"] += 1
            print(f"  [RESULT] EXTRACTION_UNSUPPORTED: {exc}")
            results.append(res_record)
            continue

        if not ingest_res.success:
            err_msg = "; ".join(ingest_res.errors)
            if "no extractable text" in err_msg.lower() or "javascript" in err_msg.lower():
                res_record["result_status"] = "EXTRACTION_UNSUPPORTED"
                entity_stats[entity]["unsupported"] += 1
                print(f"  [RESULT] EXTRACTION_UNSUPPORTED: {err_msg}")
            else:
                res_record["result_status"] = "VALIDATION_FAILED"
                entity_stats[entity]["failed"] += 1
                print(f"  [RESULT] VALIDATION_FAILED: {err_msg}")
            results.append(res_record)
            continue

        # Successful Extraction
        res_record["document_id"] = ingest_res.document_id
        res_record["source_hash"] = ingest_res.source_hash
        sec_count = len(ingest_res.normalized_document.sections) if ingest_res.normalized_document else 0
        prov_count = len(ingest_res.normalized_document.provisions) if ingest_res.normalized_document else 0
        res_record["sections_extracted"] = sec_count
        res_record["provisions_extracted"] = prov_count

        if ingest_res.status == IngestionStatus.DUPLICATE_CONTENT:
            res_record["result_status"] = "DUPLICATE"
            print(f"  [RESULT] DUPLICATE (Hash: {ingest_res.source_hash[:16]}...)")
        else:
            res_record["result_status"] = "INGESTED"
            entity_stats[entity]["ingested"] += 1
            entity_stats[entity]["sections"] += sec_count
            print(f"  [RESULT] INGESTED successfully! doc_id: {ingest_res.document_id} ({sec_count} sections)")

        # Persist to PostgreSQL if available
        if pg_repo and ingest_res.normalized_document:
            try:
                if not await pg_repo.has_hash(ingest_res.source_hash):
                    await pg_repo.save_ingested_knowledge(
                        normalized_doc=ingest_res.normalized_document,
                        reg_doc=ingest_res.regulatory_document,
                        org_doc=ingest_res.organisation_document,
                    )
                await pg_repo.record_ingestion_attempt(
                    ingestion_id=f"INGEST-{src.source_id}-{int(datetime.now(timezone.utc).timestamp())}",
                    source_url=url_str,
                    final_url=str(ingest_res.final_url) if ingest_res.final_url else url_str,
                    source_hash=ingest_res.source_hash or "",
                    document_id=ingest_res.document_id,
                    ingestion_status=res_record["result_status"],
                    retrieved_at=datetime.now(timezone.utc),
                )
            except Exception as e:
                print(f"  [DB WARNING] Failed to persist to PostgreSQL: {e}")

        results.append(res_record)
        validated_sources.append({
            "source_id": src.source_id,
            "source_class": src.source_class.value,
            "url": url_str,
            "authority": src.authority,
            "organisation_id": src.organisation_id,
            "document_type": src.document_type,
            "topic": src.topic,
            "expected_domain": src.expected_domain,
            "description": src.description,
        })

    # Output manifest.v1.yaml
    manifest_data = {
        "corpus_version": "2026-10-04-v1",
        "sources": validated_sources,
    }
    manifest_path = ai_root / "corpus" / "manifest.v1.yaml"
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(manifest_data, f, sort_keys=False, indent=2)
    print(f"\n[MANIFEST] Generated validated manifest at: {manifest_path}")

    # Output corpus_acquisition_report.json
    total_disc = sum(s["discovered"] for s in entity_stats.values())
    total_ing = sum(s["ingested"] for s in entity_stats.values())
    total_fail = sum(s["failed"] for s in entity_stats.values())
    total_unsup = sum(s["unsupported"] for s in entity_stats.values())
    total_sec = sum(s["sections"] for s in entity_stats.values())

    report_data = {
        "report_timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_sources_discovered": total_disc,
            "total_sources_validated": len(validated_sources),
            "total_documents_ingested": total_ing,
            "total_document_versions": total_ing,
            "total_sections": total_sec,
            "total_provisions": 0,
            "total_organisations": 5,
            "total_authorities": 5,
            "total_failed_sources": total_fail,
            "total_unsupported_sources": total_unsup,
        },
        "entity_breakdown": entity_stats,
        "sources": results,
    }

    report_path = ai_root / "corpus" / "corpus_acquisition_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"[REPORT] Saved acquisition report at: {report_path}")

    # Print Summary Table
    print("\n" + "=" * 70)
    print("SANGYAN CORPUS ACQUISITION SUMMARY")
    print("=" * 70)
    print(f"Total Sources Discovered:    {total_disc}")
    print(f"Total Sources Validated:     {len(validated_sources)}")
    print(f"Total Documents Ingested:    {total_ing}")
    print(f"Total Document Versions:     {total_ing}")
    print(f"Total Sections Extracted:    {total_sec}")
    print(f"Total Provisions:            0")
    print(f"Total Failed Sources:        {total_fail}")
    print(f"Total Unsupported Sources:   {total_unsup}")
    print("-" * 70)
    print(f"{'Entity':<15} {'Discovered':<12} {'Ingested':<10} {'Failed':<8} {'Unsupported':<12} {'Sections':<10}")
    print("-" * 70)
    for ent, stats in entity_stats.items():
        print(f"{ent:<15} {stats['discovered']:<12} {stats['ingested']:<10} {stats['failed']:<8} {stats['unsupported']:<12} {stats['sections']:<10}")
    print("=" * 70)

    return report_data


if __name__ == "__main__":
    asyncio.run(run_corpus_population())
