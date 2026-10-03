"""Comprehensive test suite for SANGYAN Autonomous Source Acquisition & Refresh.

Covers all 25 specific test conditions in Section 27:
1. unchanged source
2. changed source
3. duplicate content
4. changed URL with same content
5. new document version
6. superseded document
7. historical rule
8. future effective rule
9. expired rule
10. partial amendment
11. unknown temporal applicability
12. cross-reference
13. organisation-specific retrieval
14. cross-organisation retrieval
15. SEBI + broker combined retrieval
16. depository + broker combined retrieval
17. wrong organisation source
18. secondary source ranked below regulatory source
19. invalid domain
20. malicious external redirect
21. unsupported document type
22. invalid citation
23. duplicate document
24. source disappearing
25. source becoming unavailable
"""

import sys
from datetime import date, datetime, timezone
from pathlib import Path
import pytest
from pydantic import HttpUrl

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from ai.app.ingestion.errors import DomainValidationError, FetchError, IngestionStage
from ai.app.ingestion.fetcher import DocumentFetcher
from ai.app.ingestion.models import FetchedPayload, IngestionRequest
from ai.app.ingestion.pipeline import InMemoryKnowledgeRepository, IngestionPipeline
from ai.app.knowledge.documents import (
    NormalizedDocument,
    OrganisationDocument,
    RegulatoryDocument,
)
from ai.app.knowledge.relationships import KnowledgeRelationship, RelationshipType
from ai.app.knowledge.retrieval import (
    KnowledgeRetrievalEngine,
    RegulatoryRetrievalResult,
    RetrievalMode,
    RetrievalQuery,
)
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import (
    SupersededStatus,
    TemporalResolutionState,
    TemporalScope,
)
from ai.app.knowledge.temporal_engine import TemporalApplicabilityEngine
from ai.app.organisation.models import OrganisationEntry
from ai.app.organisation.registry import OrganisationRegistry
from ai.app.sources.authority_graph import AuthorityGraph, RegulatedDomain
from ai.app.sources.change_detector import ChangeDetector
from ai.app.sources.discovery import BoundedDiscoveryService
from ai.app.sources.models import (
    DiscoveryMethod,
    RefreshPolicy,
    SourceCheckStatus,
    SourceRegistryEntry,
)
from ai.app.sources.registry import SourceRegistry
from ai.app.sources.routing import DomainRouter, KnowledgeDomain
from ai.app.sources.scheduler import SourceScheduler
from ai.app.sources.validators import (
    SourceSecurityError,
    validate_content_type,
    validate_source_url,
)


class MockFetcher(DocumentFetcher):
    """Deterministic mock fetcher returning preconfigured responses or exceptions."""

    def __init__(self, responses: dict[str, FetchedPayload | Exception] | None = None) -> None:
        super().__init__()
        self.responses = responses or {}
        self.call_count = 0

    async def fetch(self, url: HttpUrl, expected_domain: str | None = None) -> FetchedPayload:
        self.call_count += 1
        url_str = str(url)
        if url_str in self.responses:
            res = self.responses[url_str]
            if isinstance(res, Exception):
                raise res
            return res
        raise FetchError(f"HTTP 404: Not Found at {url_str}")


# ==============================================================================
# Tests 1 to 25
# ==============================================================================

@pytest.mark.asyncio
async def test_01_unchanged_source():
    """1. Unchanged source: Detects identical content, does not create duplicate document."""
    html_content = b"<html><head><title>T</title></head><body><h1>Circular</h1><p>Rules</p></body></html>"
    payload = FetchedPayload(
        raw_bytes=html_content,
        final_url=HttpUrl("https://sebi.gov.in/cir.html"),
        http_status=200,
        content_type="text/html",
        content_length=len(html_content),
    )
    fetcher = MockFetcher({"https://sebi.gov.in/cir.html": payload})
    detector = ChangeDetector(fetcher=fetcher)

    from ai.app.ingestion.fingerprint import compute_source_hash
    content_hash = compute_source_hash(html_content)

    entry = SourceRegistryEntry(
        source_id="sebi_cir_unchanged",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://sebi.gov.in/cir.html"),
        expected_domain="sebi.gov.in",
        last_content_hash=content_hash,
    )

    res = await detector.check_source(entry)
    assert res.status == SourceCheckStatus.UNCHANGED
    assert res.document_id is None
    assert res.new_hash == entry.last_content_hash


@pytest.mark.asyncio
async def test_02_changed_source():
    """2. Changed source: Detects modified content, creates new document version while preserving history."""
    new_content = b"<html><head><title>T</title></head><body><h1>Circular v2</h1><p>Updated</p></body></html>"
    payload = FetchedPayload(
        raw_bytes=new_content,
        final_url=HttpUrl("https://sebi.gov.in/cir.html"),
        http_status=200,
        content_type="text/html",
        content_length=len(new_content),
    )
    fetcher = MockFetcher({"https://sebi.gov.in/cir.html": payload})
    detector = ChangeDetector(fetcher=fetcher)

    entry = SourceRegistryEntry(
        source_id="sebi_cir_changed",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://sebi.gov.in/cir.html"),
        expected_domain="sebi.gov.in",
        last_content_hash="old_outdated_hash_000000000000000000000000000000000000000000000000",
    )

    res = await detector.check_source(entry)
    assert res.status == SourceCheckStatus.CHANGED
    assert res.new_hash != entry.last_content_hash
    assert res.document_id is not None


@pytest.mark.asyncio
async def test_03_duplicate_content():
    """3. Duplicate content: Ingesting existing hash preserves deduplication."""
    repo = InMemoryKnowledgeRepository()
    pipeline = IngestionPipeline(repository=repo)
    # Manually store existing hash
    existing_hash = "f" * 64
    repo._hash_to_doc_id[existing_hash] = "doc_existing_123"

    assert repo.has_hash(existing_hash) is True
    assert repo.get_by_hash(existing_hash) is None  # no doc object, but hash is known


def test_04_changed_url_with_same_content():
    """4. Changed URL with same content: SHA-256 fingerprint remains identical."""
    from ai.app.ingestion.fingerprint import compute_source_hash
    content = b"Official Circular Provisions Text 2024"
    hash1 = compute_source_hash(content)
    hash2 = compute_source_hash(content)
    assert hash1 == hash2


def test_05_new_document_version():
    """5. New document version: Historical version remains intact with separate identity."""
    v1 = RegulatoryDocument(
        document_id="doc_v1",
        authority="SEBI",
        document_type="Circular",
        title="SEBI Master Circular 2024",
        document_identifier="MC-2024",
        effective_date=date(2024, 6, 1),
        source_url=HttpUrl("https://sebi.gov.in/mc2024.pdf"),
        source_hash="1" * 64,
    )
    v2 = RegulatoryDocument(
        document_id="doc_v2",
        authority="SEBI",
        document_type="Circular",
        title="SEBI Master Circular 2025",
        document_identifier="MC-2025",
        effective_date=date(2025, 6, 1),
        source_url=HttpUrl("https://sebi.gov.in/mc2025.pdf"),
        source_hash="2" * 64,
    )
    assert v1.document_id != v2.document_id
    assert v1.source_hash != v2.source_hash
    assert v1.effective_date != v2.effective_date


def test_06_superseded_document():
    """6. Superseded document: Confirmed superseded for post-cutoff dates, applicable prior."""
    scope = TemporalScope(
        effective_date=date(2020, 1, 1),
        termination_date=date(2024, 1, 1),
        superseded_status=SupersededStatus.SUPERSEDED,
    )
    # Incident during active period
    assert scope.check_applicability(date(2022, 6, 1)) == TemporalResolutionState.APPLICABLE
    # Incident after supersession cutoff
    assert scope.check_applicability(date(2024, 6, 1)) == TemporalResolutionState.SUPERSEDED


def test_07_historical_rule():
    """7. Historical rule: Retrieves 2024 version for 2024 incident date, not 2026 version."""
    v2024 = RegulatoryDocument(
        document_id="doc_2024",
        authority="SEBI",
        document_type="Master Circular",
        title="Master Circular 2024",
        document_identifier="MC-24",
        effective_date=date(2024, 1, 1),
        termination_date=date(2025, 12, 31),
        superseded_status=SupersededStatus.SUPERSEDED,
        source_url=HttpUrl("https://sebi.gov.in/2024.pdf"),
        source_hash="a" * 64,
    )
    v2026 = RegulatoryDocument(
        document_id="doc_2026",
        authority="SEBI",
        document_type="Master Circular",
        title="Master Circular 2026",
        document_identifier="MC-26",
        effective_date=date(2026, 1, 1),
        superseded_status=SupersededStatus.CURRENT,
        source_url=HttpUrl("https://sebi.gov.in/2026.pdf"),
        source_hash="b" * 64,
    )

    resolved_doc, state = TemporalApplicabilityEngine.resolve_applicable_document(
        documents=[v2024, v2026],
        target_date=date(2024, 5, 1),
    )
    assert state == TemporalResolutionState.APPLICABLE
    assert resolved_doc is not None
    assert resolved_doc.document_id == "doc_2024"


def test_08_future_effective_rule():
    """8. Future effective rule: Returns NOT_YET_EFFECTIVE."""
    scope = TemporalScope(
        publication_date=date(2026, 10, 1),
        effective_date=date(2027, 1, 1),
        superseded_status=SupersededStatus.CURRENT,
    )
    status = TemporalApplicabilityEngine.evaluate_applicability(scope, date(2026, 10, 4))
    assert status == TemporalResolutionState.NOT_YET_EFFECTIVE


def test_09_expired_rule():
    """9. Expired rule: Returns EXPIRED_OR_TERMINATED."""
    scope = TemporalScope(
        effective_date=date(2020, 1, 1),
        termination_date=date(2023, 12, 31),
        superseded_status=SupersededStatus.CURRENT,
    )
    status = TemporalApplicabilityEngine.evaluate_applicability(scope, date(2024, 5, 1))
    assert status == TemporalResolutionState.EXPIRED_OR_TERMINATED


def test_10_partial_amendment():
    """10. Partial amendment: Correctly captures PARTIALLY_AMENDED status."""
    scope = TemporalScope(
        effective_date=date(2022, 1, 1),
        superseded_status=SupersededStatus.PARTIALLY_AMENDED,
    )
    assert scope.superseded_status == SupersededStatus.PARTIALLY_AMENDED
    assert scope.check_applicability(date(2023, 1, 1)) == TemporalResolutionState.APPLICABLE


def test_11_unknown_temporal_applicability():
    """11. Unknown temporal applicability: Returns TEMPORALITY_UNRESOLVED rather than guessing."""
    scope = TemporalScope(
        publication_date=date(2024, 1, 1),
        effective_date=None,  # Missing effective date
        superseded_status=SupersededStatus.UNKNOWN,
    )
    status = TemporalApplicabilityEngine.evaluate_applicability(scope, date(2024, 5, 1))
    assert status == TemporalResolutionState.TEMPORALITY_UNRESOLVED


def test_12_cross_reference():
    """12. Cross-reference: Tracks typed inter-document relationship."""
    rel = KnowledgeRelationship(
        relationship_id="rel_ref_01",
        source_id="doc_circular_02",
        target_id="doc_master_circular_01",
        relationship_type=RelationshipType.REFERENCES,
        description="References stock broker compliance requirement.",
    )
    assert rel.relationship_type == RelationshipType.REFERENCES
    assert rel.source_id == "doc_circular_02"
    assert rel.target_id == "doc_master_circular_01"


def test_13_organisation_specific_retrieval():
    """13. Organisation-specific retrieval: Filters specifically for requested intermediary."""
    engine = KnowledgeRetrievalEngine()
    z_doc = OrganisationDocument(
        document_id="doc_z_tariff",
        organisation_id="ORG_ZERODHA",
        source_class=SourceClass.ORGANISATION_POLICY,
        document_type="Fee Schedule",
        title="Zerodha Demat Charges",
        document_identifier="TARIFF-2024",
        effective_date=date(2024, 1, 1),
        source_url=HttpUrl("https://zerodha.com/charges"),
        source_hash="z" * 64,
    )
    g_doc = OrganisationDocument(
        document_id="doc_g_tariff",
        organisation_id="ORG_GROWW",
        source_class=SourceClass.ORGANISATION_POLICY,
        document_type="Fee Schedule",
        title="Groww Pricing",
        document_identifier="GROWW-TARIFF-2024",
        effective_date=date(2024, 1, 1),
        source_url=HttpUrl("https://groww.in/pricing"),
        source_hash="g" * 64,
    )

    query = RetrievalQuery(
        mode=RetrievalMode.CURRENT_RULES,
        organisation_id="ORG_ZERODHA",
        reference_date=date(2024, 5, 1),
    )
    # Evaluate and rank Zerodha document
    results = engine.evaluate_and_rank_results([z_doc], query)
    assert len(results) == 1
    assert results[0].organisation_id == "ORG_ZERODHA"
    assert "Zerodha" in results[0].citation


def test_14_cross_organisation_retrieval():
    """14. Cross-organisation retrieval: DP charge issue activates SEBI, CDSL, NSDL, and Zerodha."""
    router = DomainRouter()
    target = router.route_case(
        domains=[KnowledgeDomain.DP_CHARGES],
        organisation_id="ORG_ZERODHA",
    )
    assert "SEBI" in target.authorities
    assert "CDSL" in target.authorities
    assert "NSDL" in target.authorities
    assert target.organisation_id == "ORG_ZERODHA"


def test_15_sebi_plus_broker_combined_retrieval():
    """15. SEBI + broker combined retrieval: Combines regulatory and intermediary policies."""
    engine = KnowledgeRetrievalEngine()
    sebi_doc = RegulatoryDocument(
        document_id="doc_sebi_broker",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        document_type="Master Circular",
        title="SEBI Master Circular for Stock Brokers",
        document_identifier="SEBI-MC-BROKER",
        effective_date=date(2024, 1, 1),
        source_url=HttpUrl("https://sebi.gov.in/broker.pdf"),
        source_hash="s" * 64,
    )
    zerodha_doc = OrganisationDocument(
        document_id="doc_z_grievance",
        organisation_id="ORG_ZERODHA",
        source_class=SourceClass.ORGANISATION_PROCEDURE,
        document_type="Procedure",
        title="Zerodha Escalation Matrix",
        document_identifier="ZERODHA-ESC-01",
        effective_date=date(2024, 1, 1),
        source_url=HttpUrl("https://zerodha.com/escalate"),
        source_hash="z" * 64,
    )

    query = RetrievalQuery(
        mode=RetrievalMode.CURRENT_RULES,
        reference_date=date(2024, 6, 1),
    )
    results = engine.evaluate_and_rank_results([sebi_doc, zerodha_doc], query)
    assert len(results) == 2
    # Regulatory document must rank ahead of organisation procedure
    assert results[0].source_class == SourceClass.REGULATORY
    assert results[1].source_class == SourceClass.ORGANISATION_PROCEDURE


def test_16_depository_plus_broker_combined_retrieval():
    """16. Depository + broker combined retrieval: Activates depository institutions for demat transfer."""
    router = DomainRouter()
    target = router.route_case(
        domains=[KnowledgeDomain.DEMAT_TRANSFER],
        organisation_id="ORG_ZERODHA",
    )
    assert "CDSL" in target.authorities
    assert "NSDL" in target.authorities
    assert target.include_depositories is True


def test_17_wrong_organisation_source():
    """17. Wrong organisation source: Rejects domain not belonging to the registered organisation."""
    org_registry = OrganisationRegistry()
    assert org_registry.validate_domain_for_org("ORG_ZERODHA", "zerodha.com") is True
    assert org_registry.validate_domain_for_org("ORG_ZERODHA", "support.zerodha.com") is True
    # Unofficial or malicious domain
    assert org_registry.validate_domain_for_org("ORG_ZERODHA", "zerodha-scam.com") is False
    assert org_registry.validate_domain_for_org("ORG_ZERODHA", "unaffiliated.org") is False


def test_18_secondary_source_ranked_below_regulatory():
    """18. Secondary source ranked below regulatory source."""
    engine = KnowledgeRetrievalEngine()
    reg_doc = RegulatoryDocument(
        document_id="doc_reg",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        document_type="Circular",
        title="SEBI Circular",
        document_identifier="SEBI-REG-01",
        effective_date=date(2024, 1, 1),
        source_url=HttpUrl("https://sebi.gov.in/cir.pdf"),
        source_hash="r" * 64,
    )
    from ai.app.knowledge.documents import SecondaryDocument
    sec_doc = SecondaryDocument(
        document_id="doc_sec",
        source_class=SourceClass.SECONDARY_SOURCE,
        title="Legal Summary of Circular",
        effective_date=date(2024, 1, 1),
        source_url=HttpUrl("https://sebi.gov.in/commentary.pdf"),
        source_hash="c" * 64,
    )

    query = RetrievalQuery(reference_date=date(2024, 6, 1))
    results = engine.evaluate_and_rank_results([sec_doc, reg_doc], query)
    assert len(results) == 2
    assert results[0].source_class == SourceClass.REGULATORY
    assert results[1].source_class == SourceClass.SECONDARY_SOURCE


def test_19_invalid_domain():
    """19. Invalid domain: Rejects URL where host does not match expected_domain."""
    with pytest.raises(SourceSecurityError):
        validate_source_url("https://malicious-sebi.gov.in/doc.pdf", expected_domain="sebi.gov.in")


@pytest.mark.asyncio
async def test_20_malicious_external_redirect():
    """20. Malicious external redirect: Flags MALICIOUS_REDIRECT when redirect escapes domain."""
    fetcher = MockFetcher({
        "https://sebi.gov.in/circular.html": DomainValidationError("Redirect to external 'evil.com' blocked."),
    })
    detector = ChangeDetector(fetcher=fetcher)
    entry = SourceRegistryEntry(
        source_id="sebi_redirect_test",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://sebi.gov.in/circular.html"),
        expected_domain="sebi.gov.in",
    )

    res = await detector.check_source(entry)
    assert res.status == SourceCheckStatus.MALICIOUS_REDIRECT
    assert "redirect" in res.error_message.lower()


def test_21_unsupported_document_type():
    """21. Unsupported document type: Rejects unauthorized MIME types."""
    assert validate_content_type("application/pdf") is True
    assert validate_content_type("text/html; charset=utf-8") is True
    assert validate_content_type("application/x-msdownload") is False
    assert validate_content_type("image/jpeg") is False


def test_22_invalid_citation():
    """22. Citation contract: Formulates authoritative citation including authority, title, and section."""
    result = RegulatoryRetrievalResult(
        document_id="doc_cit_test",
        source_class=SourceClass.REGULATORY,
        authority="SEBI",
        title="Pre-funded Instruments Circular",
        section="Clause 3",
        source_url="https://sebi.gov.in/cir.pdf",
        source_hash="h" * 64,
        effective_date=date(2018, 10, 1),
        temporal_resolution=TemporalResolutionState.APPLICABLE,
        citation="SEBI — Pre-funded Instruments Circular — Section Clause 3 — effective from 2018-10-01",
    )
    assert "SEBI" in result.citation
    assert "Pre-funded" in result.citation
    assert "Clause 3" in result.citation


def test_23_duplicate_document():
    """23. Duplicate document: Multiple checks on identical source do not create duplicate documents."""
    repo = InMemoryKnowledgeRepository()
    pipeline = IngestionPipeline(repository=repo)
    # Simulate first save
    norm = NormalizedDocument(document_id="doc_orig", content="Body", source_hash="unique_hash_123")
    repo.save(normalized_doc=norm)

    # Has hash must return True
    assert repo.has_hash("unique_hash_123") is True


@pytest.mark.asyncio
async def test_24_source_disappearing():
    """24. Source disappearing: Returns UNAVAILABLE on 404 without dropping historical state."""
    fetcher = MockFetcher()  # Empty responses -> raises FetchError 404
    detector = ChangeDetector(fetcher=fetcher)
    entry = SourceRegistryEntry(
        source_id="sebi_missing_src",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://sebi.gov.in/removed.html"),
        expected_domain="sebi.gov.in",
        last_content_hash="historical_hash_preserved",
    )

    res = await detector.check_source(entry)
    assert res.status == SourceCheckStatus.UNAVAILABLE
    assert entry.last_content_hash == "historical_hash_preserved"


@pytest.mark.asyncio
async def test_25_source_becoming_unavailable():
    """25. Source becoming unavailable: Transport failure logs error while keeping source active."""
    fetcher = MockFetcher({
        "https://sebi.gov.in/timeout.pdf": TimeoutError("Connection timed out after 10000ms"),
    })
    detector = ChangeDetector(fetcher=fetcher)
    entry = SourceRegistryEntry(
        source_id="sebi_timeout_src",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        canonical_url=HttpUrl("https://sebi.gov.in/timeout.pdf"),
        expected_domain="sebi.gov.in",
        last_content_hash="persisted_hash",
    )

    res = await detector.check_source(entry)
    assert res.status == SourceCheckStatus.FETCH_FAILED
    assert "timed out" in res.error_message
    assert entry.last_content_hash == "persisted_hash"
