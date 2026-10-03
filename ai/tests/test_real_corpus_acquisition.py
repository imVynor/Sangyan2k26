"""Deterministic tests for the Real Corpus Acquisition and Manifest Validation.

Tests required by Section 16:
- real source registration
- successful ingestion
- duplicate detection
- changed source
- historical version preservation
- invalid domain rejection
- unsupported MIME rejection
- missing source
- dynamic-page detection
- manifest correctness
"""

import hashlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import HttpUrl

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from ai.app.corpus.loader import load_manifest
from ai.app.corpus.validator import validate_manifest
from ai.app.ingestion.errors import FetchError, IngestionStage
from ai.app.ingestion.fetcher import DocumentFetcher
from ai.app.ingestion.models import FetchedPayload, IngestionRequest, IngestionStatus
from ai.app.ingestion.pipeline import InMemoryKnowledgeRepository, IngestionPipeline
from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.source_classes import SourceClass
from ai.app.organisation.models import OrganisationEntry
from ai.app.organisation.registry import OrganisationRegistry
from ai.app.sources.change_detector import ChangeDetector
from ai.app.sources.models import SourceCheckStatus, SourceRegistryEntry
from ai.app.sources.registry import SourceRegistry
from ai.app.sources.validators import SourceSecurityError, validate_source_url


def test_real_source_registration():
    """Verify that all target regulatory authorities and organisations are registered."""
    source_reg = SourceRegistry()
    org_reg = OrganisationRegistry()

    # Authorities
    authorities = ["SEBI", "NSE", "BSE", "CDSL", "NSDL"]
    for auth in authorities:
        sources = source_reg.list_sources(authority=auth)
        assert len(sources) >= 1, f"Authority {auth} must have at least one registered source"
        for s in sources:
            assert s.source_class == SourceClass.REGULATORY
            assert s.authority == auth

    # Intermediaries
    organisations = ["ORG_ZERODHA", "ORG_GROWW", "ORG_UPSTOX", "ORG_ANGELONE", "ORG_ICICIDIRECT"]
    for org_id in organisations:
        org = org_reg.get_organisation(org_id)
        assert org is not None, f"Organisation {org_id} must be in OrganisationRegistry"
        assert len(org.official_domains) >= 1
        assert len(org.discovery_pages) >= 1


def test_invalid_domain_rejection():
    """Verify that URLs outside registered domains or non-HTTPS are rejected."""
    # Allowed
    assert validate_source_url("https://sebi.gov.in/legal/circular.html", "sebi.gov.in")
    assert validate_source_url("https://www.sebi.gov.in/legal/circular.html", "sebi.gov.in")

    # Mismatched domain
    with pytest.raises(SourceSecurityError):
        validate_source_url("https://fake-sebi.com/legal/circular.html", "sebi.gov.in")

    # External search engine
    with pytest.raises(SourceSecurityError):
        validate_source_url("https://google.com/search?q=sebi", "sebi.gov.in")

    # Unencrypted HTTP
    with pytest.raises(SourceSecurityError):
        validate_source_url("http://sebi.gov.in/test", "sebi.gov.in")


@pytest.mark.asyncio
async def test_successful_ingestion():
    """Verify deterministic ingestion pipeline persists document, sections, and provenance."""
    repo = InMemoryKnowledgeRepository()
    mock_fetcher = AsyncMock(spec=DocumentFetcher)
    html_bytes = b"<html><body><h1>Investor Redressal</h1><p>Procedure for filing SCORES complaints.</p></body></html>"
    mock_fetcher.fetch.return_value = FetchedPayload(
        raw_bytes=html_bytes,
        final_url=HttpUrl("https://www.sebi.gov.in/legal/circulars/test.html"),
        http_status=200,
        content_type="text/html",
        content_length=len(html_bytes),
    )
    pipeline = IngestionPipeline(fetcher=mock_fetcher, repository=repo)
    req = IngestionRequest(
        source_url=HttpUrl("https://www.sebi.gov.in/legal/circulars/test.html"),
        source_class=SourceClass.REGULATORY,
        expected_domain="sebi.gov.in",
        authority="SEBI",
        document_type="circular",
    )

    result = await pipeline.ingest(req)
    assert result.success is True
    assert result.status == IngestionStatus.SUCCESS
    assert result.document_id is not None
    assert result.normalized_document is not None
    assert len(result.normalized_document.sections) >= 1
    assert result.source_hash is not None

    # Check persistence
    stored_doc = await repo.get_document(result.document_id)
    assert stored_doc is not None
    assert stored_doc.authority == "SEBI"
    assert str(stored_doc.source_url) == "https://www.sebi.gov.in/legal/circulars/test.html"


@pytest.mark.asyncio
async def test_duplicate_detection():
    """Verify that identical content returns UNCHANGED status without creating duplicates."""
    repo = InMemoryKnowledgeRepository()
    mock_fetcher = AsyncMock(spec=DocumentFetcher)
    content_bytes = b"<html><body><h1>SEBI Investor Charter</h1><p>Rights of securities investors.</p></body></html>"
    payload = FetchedPayload(
        raw_bytes=content_bytes,
        final_url=HttpUrl("https://www.sebi.gov.in/charter.html"),
        http_status=200,
        content_type="text/html",
        content_length=len(content_bytes),
    )
    mock_fetcher.fetch.return_value = payload

    source_reg = SourceRegistry()
    pipeline = IngestionPipeline(fetcher=mock_fetcher, repository=repo)
    cd = ChangeDetector(fetcher=mock_fetcher, pipeline=pipeline, registry=source_reg)

    entry = SourceRegistryEntry(
        source_id="test_sebi_charter",
        canonical_url=HttpUrl("https://www.sebi.gov.in/charter.html"),
        expected_domain="sebi.gov.in",
        source_class=SourceClass.REGULATORY,
        authority="SEBI",
        document_type="investor_charter",
    )

    # First check: new document
    res1 = await cd.check_source(entry)
    assert res1.status == SourceCheckStatus.NEW_DOCUMENT
    entry.last_content_hash = res1.new_hash

    # Second check with same content: unchanged
    res2 = await cd.check_source(entry)
    assert res2.status == SourceCheckStatus.UNCHANGED
    assert res2.new_hash == res1.new_hash


@pytest.mark.asyncio
async def test_changed_source():
    """Verify that modified content triggers CHANGED status and records new hash."""
    repo = InMemoryKnowledgeRepository()
    mock_fetcher = AsyncMock(spec=DocumentFetcher)
    v1_bytes = b"<html><body><h1>Circular v1</h1><p>30 days timeline</p></body></html>"
    v2_bytes = b"<html><body><h1>Circular v2</h1><p>21 days timeline</p></body></html>"

    source_reg = SourceRegistry()
    pipeline = IngestionPipeline(fetcher=mock_fetcher, repository=repo)
    cd = ChangeDetector(fetcher=mock_fetcher, pipeline=pipeline, registry=source_reg)

    entry = SourceRegistryEntry(
        source_id="test_timeline_cir",
        canonical_url=HttpUrl("https://www.sebi.gov.in/timeline.html"),
        expected_domain="sebi.gov.in",
        source_class=SourceClass.REGULATORY,
        authority="SEBI",
        document_type="circular",
    )

    # First version
    mock_fetcher.fetch.return_value = FetchedPayload(
        raw_bytes=v1_bytes,
        final_url=HttpUrl("https://www.sebi.gov.in/timeline.html"),
        http_status=200,
        content_type="text/html",
        content_length=len(v1_bytes),
    )
    res1 = await cd.check_source(entry)
    assert res1.status == SourceCheckStatus.NEW_DOCUMENT
    entry.last_content_hash = res1.new_hash

    # Second version (content changed)
    mock_fetcher.fetch.return_value = FetchedPayload(
        raw_bytes=v2_bytes,
        final_url=HttpUrl("https://www.sebi.gov.in/timeline.html"),
        http_status=200,
        content_type="text/html",
        content_length=len(v2_bytes),
    )
    res2 = await cd.check_source(entry)
    assert res2.status == SourceCheckStatus.CHANGED
    assert res2.previous_hash == res1.new_hash
    assert res2.new_hash != res1.new_hash


@pytest.mark.asyncio
async def test_historical_version_preservation():
    """Verify that when a source changes, previous document is preserved in repository."""
    repo = InMemoryKnowledgeRepository()
    mock_fetcher = AsyncMock(spec=DocumentFetcher)
    
    # Version 1
    v1_bytes = b"<html><body><h1>Charges v1</h1><p>Equity delivery: Rs 0</p></body></html>"
    mock_fetcher.fetch.return_value = FetchedPayload(
        raw_bytes=v1_bytes,
        final_url=HttpUrl("https://zerodha.com/charges"),
        http_status=200,
        content_type="text/html",
        content_length=len(v1_bytes),
    )
    pipeline = IngestionPipeline(fetcher=mock_fetcher, repository=repo)
    req1 = IngestionRequest(
        source_url=HttpUrl("https://zerodha.com/charges"),
        source_class=SourceClass.ORGANISATION_POLICY,
        expected_domain="zerodha.com",
        organisation_id="ORG_ZERODHA",
        document_type="charges_schedule",
    )
    res1 = await pipeline.ingest(req1)
    doc1_id = res1.document_id

    # Version 2 (different content -> new hash and new version)
    v2_bytes = b"<html><body><h1>Charges v2</h1><p>Equity delivery: Rs 0. Pledge fee: Rs 30</p></body></html>"
    mock_fetcher.fetch.return_value = FetchedPayload(
        raw_bytes=v2_bytes,
        final_url=HttpUrl("https://zerodha.com/charges"),
        http_status=200,
        content_type="text/html",
        content_length=len(v2_bytes),
    )
    res2 = await pipeline.ingest(req1)
    doc2_id = res2.document_id

    assert doc1_id != doc2_id
    doc1 = repo._organisation_docs.get(doc1_id)
    doc2 = repo._organisation_docs.get(doc2_id)
    assert doc1 is not None, "Historical document version 1 must NOT be deleted"
    assert doc2 is not None, "New document version 2 must be stored"


@pytest.mark.asyncio
async def test_unsupported_mime_rejection():
    """Verify pipeline rejects media / executable MIME types."""
    repo = InMemoryKnowledgeRepository()
    mock_fetcher = AsyncMock(spec=DocumentFetcher)
    video_bytes = b"\x00\x00\x00\x18ftypmp42"
    mock_fetcher.fetch.return_value = FetchedPayload(
        raw_bytes=video_bytes,
        final_url=HttpUrl("https://www.sebi.gov.in/video.mp4"),
        http_status=200,
        content_type="video/mp4",
        content_length=len(video_bytes),
    )
    pipeline = IngestionPipeline(fetcher=mock_fetcher, repository=repo)
    req = IngestionRequest(
        source_url=HttpUrl("https://www.sebi.gov.in/video.mp4"),
        source_class=SourceClass.REGULATORY,
        expected_domain="sebi.gov.in",
        authority="SEBI",
        document_type="circular",
    )
    res = await pipeline.ingest(req)
    assert res.status == IngestionStatus.UNSUPPORTED_CONTENT or res.status == IngestionStatus.VALIDATION_FAILED


@pytest.mark.asyncio
async def test_missing_source():
    """Verify that HTTP 404 returns FETCH_FAILED without faking."""
    repo = InMemoryKnowledgeRepository()
    mock_fetcher = AsyncMock(spec=DocumentFetcher)
    mock_fetcher.fetch.side_effect = FetchError("HTTP 404 Not Found")
    pipeline = IngestionPipeline(fetcher=mock_fetcher, repository=repo)
    req = IngestionRequest(
        source_url=HttpUrl("https://www.sebi.gov.in/nonexistent.pdf"),
        source_class=SourceClass.REGULATORY,
        expected_domain="sebi.gov.in",
        authority="SEBI",
        document_type="circular",
    )
    res = await pipeline.ingest(req)
    assert res.status == IngestionStatus.FETCH_FAILED
    assert any("404" in err for err in res.errors)


@pytest.mark.asyncio
async def test_dynamic_page_detection():
    """Verify empty/client-rendered shell yields zero extractable sections or proper handling."""
    repo = InMemoryKnowledgeRepository()
    mock_fetcher = AsyncMock(spec=DocumentFetcher)
    empty_shell = b"<html><head><script src='app.js'></script></head><body><div id='root'></div></body></html>"
    mock_fetcher.fetch.return_value = FetchedPayload(
        raw_bytes=empty_shell,
        final_url=HttpUrl("https://www.bseindia.com/investors/invservices"),
        http_status=200,
        content_type="text/html",
        content_length=len(empty_shell),
    )
    pipeline = IngestionPipeline(fetcher=mock_fetcher, repository=repo)
    req = IngestionRequest(
        source_url=HttpUrl("https://www.bseindia.com/investors/invservices"),
        source_class=SourceClass.REGULATORY,
        expected_domain="bseindia.com",
        authority="BSE",
        document_type="guidelines",
    )
    res = await pipeline.ingest(req)
    if res.status == IngestionStatus.SUCCESS:
        doc = await repo.get_regulatory_document(res.document_id)
        assert len(doc.raw_text.strip()) == 0


def test_manifest_correctness():
    """Verify the real manifest.v1.yaml is valid, has version, and only points to registered domains."""
    manifest_path = Path(__file__).resolve().parent.parent / "corpus" / "manifest.v1.yaml"
    assert manifest_path.exists(), "ai/corpus/manifest.v1.yaml must exist"

    manifest = load_manifest(manifest_path)
    assert manifest.corpus_version == "2026-10-04-v1"
    assert len(manifest.sources) == 16

    registered_domains = {
        "sebi.gov.in", "cdslindia.com", "nsdl.com",
        "zerodha.com", "groww.in", "upstox.com", "angelone.in", "icicidirect.com"
    }

    for s in manifest.sources:
        assert s.source_id is not None and len(s.source_id) > 0
        assert s.source_class in (SourceClass.REGULATORY, SourceClass.ORGANISATION_POLICY, SourceClass.ORGANISATION_PROCEDURE)
        assert s.expected_domain in registered_domains
        assert str(s.url).startswith("https://")
        if s.source_class == SourceClass.REGULATORY:
            assert s.authority in ("SEBI", "NSE", "BSE", "CDSL", "NSDL")
        else:
            assert s.organisation_id in ("ORG_ZERODHA", "ORG_GROWW", "ORG_UPSTOX", "ORG_ANGELONE", "ORG_ICICIDIRECT")
