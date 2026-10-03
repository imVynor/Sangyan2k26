"""Comprehensive offline tests for SANGYAN Corpus Manifest System.

Verifies:
1. valid manifest
2. missing corpus version
3. empty source list
4. missing source_id
5. duplicate source_id
6. invalid URL
7. invalid source class
8. organisation source without organisation_id
9. regulatory source
10. organisation policy source
11. organisation procedure source
12. organisation FAQ source
13. expected_domain validation
14. YAML parsing
15. malformed YAML
16. dry-run performs no HTTP
17. dry-run performs no DB writes
18. runner invokes existing ingestion pipeline
19. failed source produces structured failure
20. successful source produces structured success
21. duplicate source is represented correctly
22. corpus run result totals are correct
23. exact same manifest is idempotent
24. source IDs remain stable
25. source contents are NOT embedded in manifest models
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from ai.app.corpus.loader import load_manifest, load_manifest_from_string
from ai.app.corpus.models import (
    CorpusManifest,
    CorpusRunResult,
    CorpusSource,
    SourceExecutionStatus,
    SourceRunResult,
)
from ai.app.corpus.runner import CorpusRunner
from ai.app.corpus.validator import CorpusValidationError, validate_manifest
from ai.app.ingestion.errors import FetchError, IngestionStage
from ai.app.ingestion.fetcher import DocumentFetcher
from ai.app.ingestion.models import (
    FetchedPayload,
    IngestionRequest,
    IngestionResult,
    IngestionStatus,
)
from ai.app.ingestion.pipeline import InMemoryKnowledgeRepository, IngestionPipeline
from ai.app.knowledge.documents import NormalizedDocument, RegulatoryDocument
from ai.app.knowledge.source_classes import SourceClass
from pydantic import HttpUrl


# ==============================================================================
# Helper Mock Fetcher for Unit Ingestion
# ==============================================================================

class MockDocumentFetcher(DocumentFetcher):
    """Deterministic in-memory fetcher for testing runner integration."""

    def __init__(self, responses: dict[str, FetchedPayload | Exception] | None = None) -> None:
        super().__init__()
        self.responses = responses or {}
        self.call_count = 0

    async def fetch(self, url: HttpUrl, expected_domain: str | None = None) -> FetchedPayload:
        self.call_count += 1
        url_str = str(url)
        if url_str in self.responses:
            val = self.responses[url_str]
            if isinstance(val, Exception):
                raise val
            return val
        raise FetchError(f"404 Not Found: {url_str}", stage=IngestionStage.FETCH)


# ==============================================================================
# Tests 1 to 25
# ==============================================================================

def test_01_valid_manifest():
    """1. Valid manifest with regulatory and organisation sources."""
    yaml_text = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "sebi_cir_01"
        source_class: "REGULATORY"
        authority: "SEBI"
        url: "https://sebi.gov.in/cir01.pdf"
        expected_domain: "sebi.gov.in"
      - source_id: "broker_policy_01"
        source_class: "ORGANISATION_POLICY"
        organisation_id: "ORG_ZERODHA"
        url: "https://zerodha.com/policy.html"
    """
    manifest = load_manifest_from_string(yaml_text)
    assert manifest.corpus_version == "2026-10-04-v1"
    assert len(manifest.sources) == 2
    assert manifest.sources[0].source_id == "sebi_cir_01"
    assert manifest.sources[0].source_class == SourceClass.REGULATORY
    assert manifest.sources[1].organisation_id == "ORG_ZERODHA"


def test_02_missing_corpus_version():
    """2. Rejection when corpus_version is missing or blank."""
    yaml_text = """
    sources:
      - source_id: "sebi_cir_01"
        source_class: "REGULATORY"
        url: "https://sebi.gov.in/cir01.pdf"
    """
    with pytest.raises(CorpusValidationError) as exc_info:
        load_manifest_from_string(yaml_text)
    assert "corpus_version" in str(exc_info.value).lower()


def test_03_empty_source_list():
    """3. Rejection when sources list is empty."""
    yaml_text = """
    corpus_version: "2026-10-04-v1"
    sources: []
    """
    with pytest.raises(CorpusValidationError) as exc_info:
        load_manifest_from_string(yaml_text)
    assert "empty" in str(exc_info.value).lower()


def test_04_missing_source_id():
    """4. Rejection when source_id is missing or empty."""
    yaml_text = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_class: "REGULATORY"
        url: "https://sebi.gov.in/cir01.pdf"
    """
    with pytest.raises(CorpusValidationError) as exc_info:
        load_manifest_from_string(yaml_text)
    assert "source_id" in str(exc_info.value).lower()


def test_05_duplicate_source_id():
    """5. Rejection when duplicate source_id values exist."""
    yaml_text = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "duplicate_source"
        source_class: "REGULATORY"
        url: "https://sebi.gov.in/cir01.pdf"
      - source_id: "duplicate_source"
        source_class: "ORGANISATION_POLICY"
        organisation_id: "ORG_TEST"
        url: "https://broker.com/policy.html"
    """
    with pytest.raises(CorpusValidationError) as exc_info:
        load_manifest_from_string(yaml_text)
    assert "duplicate source_id" in str(exc_info.value).lower()
    assert "duplicate_source" in str(exc_info.value)


def test_06_invalid_url():
    """6. Rejection of local file paths, malformed URLs, and credentials."""
    # Local file path
    yaml_local = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "src_local"
        source_class: "REGULATORY"
        url: "file:///etc/passwd"
    """
    with pytest.raises(CorpusValidationError):
        load_manifest_from_string(yaml_local)

    # Embedded credentials
    yaml_creds = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "src_creds"
        source_class: "REGULATORY"
        url: "https://user:secret@sebi.gov.in/doc.pdf"
    """
    with pytest.raises(CorpusValidationError):
        load_manifest_from_string(yaml_creds)

    # Non-http scheme
    yaml_ftp = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "src_ftp"
        source_class: "REGULATORY"
        url: "ftp://sebi.gov.in/doc.pdf"
    """
    with pytest.raises(CorpusValidationError):
        load_manifest_from_string(yaml_ftp)


def test_07_invalid_source_class():
    """7. Rejection of invalid source_class."""
    yaml_text = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "src_invalid"
        source_class: "UNOFFICIAL_BLOG_POST"
        url: "https://sebi.gov.in/cir01.pdf"
    """
    with pytest.raises(CorpusValidationError) as exc_info:
        load_manifest_from_string(yaml_text)
    assert "invalid 'source_class'" in str(exc_info.value).lower()


def test_08_organisation_source_without_organisation_id():
    """8. Rejection of organisation source without organisation_id."""
    yaml_text = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "broker_policy"
        source_class: "ORGANISATION_POLICY"
        url: "https://broker.com/policy.html"
    """
    with pytest.raises(CorpusValidationError) as exc_info:
        load_manifest_from_string(yaml_text)
    assert "organisation_id" in str(exc_info.value).lower()


def test_09_regulatory_source():
    """9. Regulatory source allows authority and does not require organisation_id."""
    source = CorpusSource(
        source_id="sebi_doc_01",
        source_class=SourceClass.REGULATORY,
        authority="SEBI",
        url=HttpUrl("https://sebi.gov.in/doc.pdf"),
    )
    assert source.authority == "SEBI"
    assert source.organisation_id is None


def test_10_organisation_policy_source():
    """10. Organisation policy source with valid organisation_id."""
    source = CorpusSource(
        source_id="org_policy_01",
        source_class=SourceClass.ORGANISATION_POLICY,
        organisation_id="ORG_GROWW",
        url=HttpUrl("https://groww.in/policy.html"),
    )
    assert source.organisation_id == "ORG_GROWW"
    assert source.source_class == SourceClass.ORGANISATION_POLICY


def test_11_organisation_procedure_source():
    """11. Organisation procedure source with valid organisation_id."""
    source = CorpusSource(
        source_id="org_proc_01",
        source_class=SourceClass.ORGANISATION_PROCEDURE,
        organisation_id="ORG_ANGEL",
        url=HttpUrl("https://angelone.in/procedure.html"),
    )
    assert source.source_class == SourceClass.ORGANISATION_PROCEDURE
    assert source.organisation_id == "ORG_ANGEL"


def test_12_organisation_faq_source():
    """12. Organisation FAQ source with valid organisation_id."""
    source = CorpusSource(
        source_id="org_faq_01",
        source_class=SourceClass.ORGANISATION_FAQ,
        organisation_id="ORG_UPSTOX",
        url=HttpUrl("https://upstox.com/faq.html"),
    )
    assert source.source_class == SourceClass.ORGANISATION_FAQ
    assert source.organisation_id == "ORG_UPSTOX"


def test_13_expected_domain_validation():
    """13. expected_domain validation and normalization."""
    # Valid domain normalized to lowercase
    source = CorpusSource(
        source_id="src_domain",
        source_class=SourceClass.REGULATORY,
        url=HttpUrl("https://sebi.gov.in/doc.pdf"),
        expected_domain="SEBI.GOV.IN",
    )
    assert source.expected_domain == "sebi.gov.in"

    # Invalid expected_domain containing path or scheme
    yaml_bad_domain = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "src_bad_domain"
        source_class: "REGULATORY"
        url: "https://sebi.gov.in/doc.pdf"
        expected_domain: "https://sebi.gov.in/path"
    """
    with pytest.raises(CorpusValidationError) as exc_info:
        load_manifest_from_string(yaml_bad_domain)
    assert "expected_domain" in str(exc_info.value).lower()


def test_14_yaml_parsing():
    """14. Parsing valid YAML structure into CorpusManifest."""
    yaml_text = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "src_01"
        source_class: "REGULATORY"
        url: "https://sebi.gov.in/doc.pdf"
        document_type: "Circular"
        topic:
          - investor_protection
    """
    manifest = load_manifest_from_string(yaml_text)
    assert manifest.corpus_version == "2026-10-04-v1"
    assert manifest.sources[0].topic == ["investor_protection"]


def test_15_malformed_yaml():
    """15. Rejection of malformed YAML syntax."""
    malformed_yaml = """
    corpus_version: "2026-10-04-v1"
    sources:
      - source_id: "bad_yaml
        unclosed quote
    """
    with pytest.raises(CorpusValidationError) as exc_info:
        load_manifest_from_string(malformed_yaml)
    assert "malformed yaml" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_16_dry_run_performs_no_http():
    """16. Dry run performs zero network/HTTP requests."""
    fetcher = MockDocumentFetcher()
    pipeline = IngestionPipeline(fetcher=fetcher)
    runner = CorpusRunner(pipeline=pipeline)

    manifest = CorpusManifest(
        corpus_version="2026-10-04-v1",
        sources=[
            CorpusSource(
                source_id="src_dry_1",
                source_class=SourceClass.REGULATORY,
                url=HttpUrl("https://sebi.gov.in/doc1.pdf"),
            ),
            CorpusSource(
                source_id="src_dry_2",
                source_class=SourceClass.ORGANISATION_POLICY,
                organisation_id="ORG_TEST",
                url=HttpUrl("https://broker.com/policy.html"),
            ),
        ],
    )

    result = await runner.run(manifest, dry_run=True)
    assert fetcher.call_count == 0
    assert result.total_sources == 2
    assert all(r.status == SourceExecutionStatus.DRY_RUN.value for r in result.results)


@pytest.mark.asyncio
async def test_17_dry_run_performs_no_db_writes():
    """17. Dry run performs zero repository or database mutations."""
    mock_repo = MagicMock(spec=InMemoryKnowledgeRepository)
    mock_pg_repo = AsyncMock()

    pipeline = IngestionPipeline(repository=mock_repo)
    runner = CorpusRunner(pipeline=pipeline, pg_repo=mock_pg_repo)

    manifest = CorpusManifest(
        corpus_version="2026-10-04-v1",
        sources=[
            CorpusSource(
                source_id="src_dry",
                source_class=SourceClass.REGULATORY,
                url=HttpUrl("https://sebi.gov.in/doc.pdf"),
            ),
        ],
    )

    result = await runner.run(manifest, dry_run=True)
    assert mock_repo.save.call_count == 0
    assert mock_pg_repo.save_ingested_knowledge.call_count == 0
    assert mock_pg_repo.record_ingestion_attempt.call_count == 0
    assert result.successful_sources == 0


@pytest.mark.asyncio
async def test_18_runner_invokes_existing_ingestion_pipeline():
    """18. Runner constructs IngestionRequest and invokes existing IngestionPipeline."""
    mock_pipeline = AsyncMock(spec=IngestionPipeline)
    mock_pipeline.ingest.return_value = IngestionResult(
        success=True,
        status=IngestionStatus.SUCCESS,
        document_id="doc_mock_01",
        source_hash="h" * 64,
        stage=IngestionStage.VALIDATION,
    )

    runner = CorpusRunner(pipeline=mock_pipeline)
    manifest = CorpusManifest(
        corpus_version="2026-10-04-v1",
        sources=[
            CorpusSource(
                source_id="src_01",
                source_class=SourceClass.REGULATORY,
                authority="SEBI",
                url=HttpUrl("https://sebi.gov.in/cir.pdf"),
                document_type="Circular",
            )
        ],
    )

    await runner.run(manifest, dry_run=False)

    assert mock_pipeline.ingest.call_count == 1
    call_arg = mock_pipeline.ingest.call_args[0][0]
    assert isinstance(call_arg, IngestionRequest)
    assert str(call_arg.source_url) == "https://sebi.gov.in/cir.pdf"
    assert call_arg.source_class == SourceClass.REGULATORY
    assert call_arg.authority == "SEBI"
    assert call_arg.document_type == "Circular"


@pytest.mark.asyncio
async def test_19_failed_source_produces_structured_failure():
    """19. Failed ingestion produces structured failure with error_stage and message."""
    mock_pipeline = AsyncMock(spec=IngestionPipeline)
    mock_pipeline.ingest.return_value = IngestionResult(
        success=False,
        status=IngestionStatus.FETCH_FAILED,
        stage=IngestionStage.FETCH,
        errors=["HTTP 404: Document Not Found"],
    )

    runner = CorpusRunner(pipeline=mock_pipeline)
    manifest = CorpusManifest(
        corpus_version="2026-10-04-v1",
        sources=[
            CorpusSource(
                source_id="src_fail",
                source_class=SourceClass.REGULATORY,
                url=HttpUrl("https://sebi.gov.in/missing.pdf"),
            )
        ],
    )

    result = await runner.run(manifest, dry_run=False)

    assert result.failed_sources == 1
    assert result.successful_sources == 0
    assert len(result.results) == 1
    res = result.results[0]
    assert res.status == SourceExecutionStatus.FAILED.value
    assert res.error_stage == "FETCH"
    assert "404" in res.error_message


@pytest.mark.asyncio
async def test_20_successful_source_produces_structured_success():
    """20. Successful ingestion returns document_id, source_hash, and SUCCESS status."""
    mock_pipeline = AsyncMock(spec=IngestionPipeline)
    mock_pipeline.ingest.return_value = IngestionResult(
        success=True,
        status=IngestionStatus.SUCCESS,
        document_id="doc_success_01",
        source_hash="s" * 64,
        stage=IngestionStage.VALIDATION,
    )

    runner = CorpusRunner(pipeline=mock_pipeline)
    manifest = CorpusManifest(
        corpus_version="2026-10-04-v1",
        sources=[
            CorpusSource(
                source_id="src_ok",
                source_class=SourceClass.REGULATORY,
                url=HttpUrl("https://sebi.gov.in/success.pdf"),
            )
        ],
    )

    result = await runner.run(manifest, dry_run=False)

    assert result.successful_sources == 1
    assert result.failed_sources == 0
    res = result.results[0]
    assert res.status == SourceExecutionStatus.SUCCESS.value
    assert res.document_id == "doc_success_01"
    assert res.source_hash == "s" * 64


@pytest.mark.asyncio
async def test_21_duplicate_source_is_represented_correctly():
    """21. Duplicate source produces DUPLICATE status without failing."""
    mock_pipeline = AsyncMock(spec=IngestionPipeline)
    mock_pipeline.ingest.return_value = IngestionResult(
        success=True,
        status=IngestionStatus.DUPLICATE_CONTENT,
        document_id="doc_existing_01",
        source_hash="d" * 64,
        stage=IngestionStage.DEDUPLICATION,
    )

    runner = CorpusRunner(pipeline=mock_pipeline)
    manifest = CorpusManifest(
        corpus_version="2026-10-04-v1",
        sources=[
            CorpusSource(
                source_id="src_dup",
                source_class=SourceClass.REGULATORY,
                url=HttpUrl("https://sebi.gov.in/duplicate.pdf"),
            )
        ],
    )

    result = await runner.run(manifest, dry_run=False)

    assert result.duplicate_sources == 1
    assert result.successful_sources == 0
    assert result.results[0].status == SourceExecutionStatus.DUPLICATE.value
    assert result.results[0].document_id == "doc_existing_01"


@pytest.mark.asyncio
async def test_22_corpus_run_result_totals_are_correct():
    """22. Aggregate totals correctly sum success, duplicate, and failed sources."""
    mock_pipeline = AsyncMock(spec=IngestionPipeline)
    mock_pipeline.ingest.side_effect = [
        IngestionResult(success=True, status=IngestionStatus.SUCCESS, document_id="doc_1", source_hash="1"*64),
        IngestionResult(success=True, status=IngestionStatus.DUPLICATE_CONTENT, document_id="doc_2", source_hash="2"*64),
        IngestionResult(success=False, status=IngestionStatus.FETCH_FAILED, errors=["Network timeout"], stage=IngestionStage.FETCH),
    ]

    runner = CorpusRunner(pipeline=mock_pipeline)
    manifest = CorpusManifest(
        corpus_version="2026-10-04-v1",
        sources=[
            CorpusSource(source_id="s1", source_class=SourceClass.REGULATORY, url=HttpUrl("https://sebi.gov.in/1")),
            CorpusSource(source_id="s2", source_class=SourceClass.REGULATORY, url=HttpUrl("https://sebi.gov.in/2")),
            CorpusSource(source_id="s3", source_class=SourceClass.REGULATORY, url=HttpUrl("https://sebi.gov.in/3")),
        ],
    )

    result = await runner.run(manifest, dry_run=False)

    assert result.total_sources == 3
    assert result.successful_sources == 1
    assert result.duplicate_sources == 1
    assert result.failed_sources == 1


@pytest.mark.asyncio
async def test_23_exact_same_manifest_is_idempotent():
    """23. Re-running exact same manifest produces SUCCESS first, then DUPLICATE second."""
    payload = FetchedPayload(
        raw_bytes=b"<html><head><title>Test Doc</title></head><body><h1>Heading</h1><p>Content</p></body></html>",
        final_url=HttpUrl("https://sebi.gov.in/test.html"),
        http_status=200,
        content_type="text/html",
        content_length=95,
    )
    fetcher = MockDocumentFetcher(responses={"https://sebi.gov.in/test.html": payload})
    repo = InMemoryKnowledgeRepository()
    pipeline = IngestionPipeline(fetcher=fetcher, repository=repo)
    runner = CorpusRunner(pipeline=pipeline)

    manifest = CorpusManifest(
        corpus_version="2026-10-04-v1",
        sources=[
            CorpusSource(
                source_id="idempotent_test_src",
                source_class=SourceClass.REGULATORY,
                authority="SEBI",
                url=HttpUrl("https://sebi.gov.in/test.html"),
            )
        ],
    )

    # First run: should succeed
    res1 = await runner.run(manifest, dry_run=False)
    assert res1.successful_sources == 1
    assert res1.duplicate_sources == 0
    assert res1.results[0].status == SourceExecutionStatus.SUCCESS.value

    # Second run: must detect duplicate content via SHA-256 and NOT create new document
    res2 = await runner.run(manifest, dry_run=False)
    assert res2.successful_sources == 0
    assert res2.duplicate_sources == 1
    assert res2.results[0].status == SourceExecutionStatus.DUPLICATE.value
    assert res2.results[0].source_hash == res1.results[0].source_hash


def test_24_source_ids_remain_stable():
    """24. source_ids remain verbatim without random UUID generation."""
    explicit_id = "sebi_investor_grievance_master_circular_2024"
    source = CorpusSource(
        source_id=explicit_id,
        source_class=SourceClass.REGULATORY,
        url=HttpUrl("https://sebi.gov.in/doc.pdf"),
    )
    assert source.source_id == explicit_id
    manifest = CorpusManifest(corpus_version="2026-10-04-v1", sources=[source])
    assert manifest.sources[0].source_id == explicit_id


def test_25_source_contents_are_not_embedded_in_manifest_models():
    """25. Manifest models strictly contain acquisition specifications, NOT document bodies."""
    forbidden_fields = {"content", "raw_text", "raw_bytes", "body", "sections", "extracted_text"}

    source_fields = set(CorpusSource.model_fields.keys())
    assert forbidden_fields.isdisjoint(source_fields), f"CorpusSource leaked content fields: {source_fields & forbidden_fields}"

    manifest_fields = set(CorpusManifest.model_fields.keys())
    assert forbidden_fields.isdisjoint(manifest_fields), f"CorpusManifest leaked content fields: {manifest_fields & forbidden_fields}"


# ==============================================================================
# Additional Operational Tests
# ==============================================================================

def test_load_example_manifest_from_filesystem():
    """Confirm ai/corpus/manifest.example.yaml loads and validates cleanly."""
    example_path = Path(__file__).resolve().parent.parent / "corpus" / "manifest.example.yaml"
    manifest = load_manifest(example_path)
    assert manifest.corpus_version == "2026-10-04-v1"
    assert len(manifest.sources) == 2


def test_nonexistent_manifest_file_raises():
    """Attempting to load a missing file path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_manifest("ai/corpus/non_existent_manifest.yaml")
