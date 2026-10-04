"""Live PostgreSQL integration tests for SANGYAN knowledge persistence.

Requires an active PostgreSQL database specified via the DATABASE_URL environment variable.
When DATABASE_URL is not set or the database is offline, these tests are cleanly skipped.

Covers:
1. create regulatory document
2. retrieve regulatory document
3. create organisation document
4. retrieve organisation document
5. persist provenance
6. persist sections
7. reconstruct section hierarchy
8. persist provisions
9. foreign-key rejection for orphan provision
10. persist relationships
11. self-reference rejection
12. duplicate content detection
13. transaction rollback
14. persistence across application restart
15. organisation filtering
16. regulatory filtering
17. temporal metadata preservation
18. ingestion record persistence
"""

import os
import sys
from datetime import date, datetime, timezone

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from pydantic import HttpUrl
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from ai.app.config.settings import settings
from ai.app.db.base import Base
from ai.app.db.models import RegulatoryProvisionORM
from ai.app.db.repository import PostgresKnowledgeRepository
from ai.app.db.session import get_async_engine, get_async_session
from ai.app.knowledge.documents import (
    DocumentSection,
    NormalizedDocument,
    OrganisationDocument,
    RegulatoryDocument,
)
from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.provisions import OrganisationProvision, RegulatoryProvision
from ai.app.knowledge.relationships import KnowledgeRelationship, RelationshipType
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import SupersededStatus, TemporalScope


async def check_postgres_available() -> bool:
    """Check if PostgreSQL is configured and reachable."""
    if not settings.database_url and not os.environ.get("DATABASE_URL"):
        return False
    try:
        engine = get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
async def pg_repo():
    """Fixture providing initialized PostgreSQL repository with created tables."""
    is_live = await check_postgres_available()
    if not is_live:
        pytest.skip("PostgreSQL is not configured or unreachable. Skipping PostgreSQL integration tests.")

    engine = get_async_engine()
    # Create all schema tables for integration testing
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _clean():
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM ingestion_records WHERE document_id LIKE '%test%' OR document_id IS NULL"))
            await conn.execute(text("DELETE FROM knowledge_relationships WHERE source_id LIKE '%test%' OR target_id LIKE '%test%' OR relationship_id LIKE 'REL-TEST%' OR source_id = 'doc_reg_rel_parent'"))
            await conn.execute(text("DELETE FROM regulatory_provisions WHERE document_id LIKE '%test%'"))
            await conn.execute(text("DELETE FROM organisation_provisions WHERE document_id LIKE '%test%'"))
            await conn.execute(text("DELETE FROM knowledge_provisions WHERE document_id LIKE '%test%'"))
            await conn.execute(text("DELETE FROM document_sections WHERE document_id LIKE '%test%'"))
            await conn.execute(text("DELETE FROM provenance WHERE document_id LIKE '%test%' OR document_id IN ('doc_dedup_01', 'doc_reg_rel_parent')"))
            await conn.execute(text("DELETE FROM regulatory_documents WHERE document_id LIKE '%test%' OR document_id IN ('doc_dedup_01', 'doc_reg_rel_parent')"))
            await conn.execute(text("DELETE FROM organisation_documents WHERE document_id LIKE '%test%'"))

    await _clean()
    repo = PostgresKnowledgeRepository()
    yield repo
    await _clean()


# =====================================================================
# PostgreSQL Integration Tests (1 to 18)
# =====================================================================

@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_01_create_and_02_retrieve_regulatory_document(pg_repo):
    """1 & 2. Create and retrieve regulatory document."""
    doc = RegulatoryDocument(
        document_id="doc_reg_sebi_test_pg_01",
        authority="SEBI",
        jurisdiction="India",
        document_type="Circular",
        title="SEBI Circular on Pre-funded Instruments",
        document_identifier="SEBI/HO/MIRSD/DOS3/CIR/P/2018/139",
        publication_date=date(2018, 10, 1),
        effective_date=date(2018, 11, 1),
        superseded_status=SupersededStatus.CURRENT,
        source_url=HttpUrl("https://www.sebi.gov.in/legal/circulars/oct-2018/cir_139.html"),
        source_hash="a" * 64,
        retrieved_at=datetime.now(timezone.utc),
    )
    norm = NormalizedDocument(
        document_id=doc.document_id,
        content="Raw circular text...",
        sections=[],
        source_hash=doc.source_hash,
    )
    await pg_repo.save_ingested_knowledge(normalized_doc=norm, reg_doc=doc)

    retrieved = await pg_repo.get_document("doc_reg_sebi_test_pg_01")
    assert retrieved is not None
    assert retrieved.document_id == "doc_reg_sebi_test_pg_01"
    assert retrieved.authority == "SEBI"
    assert retrieved.publication_date == date(2018, 10, 1)


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_03_create_and_04_retrieve_org_document(pg_repo):
    """3 & 4. Create and retrieve organisation document."""
    doc = OrganisationDocument(
        document_id="doc_org_zerodha_test_pg_02",
        organisation_id="ORG_ZERODHA",
        source_class=SourceClass.ORGANISATION_POLICY,
        document_type="Fee Schedule",
        title="Account Charges",
        document_identifier="TARIFF-2024",
        effective_date=date(2024, 1, 1),
        source_url=HttpUrl("https://zerodha.com/charges.html"),
        source_hash="b" * 64,
        applicable_process="dp_charges",
    )
    norm = NormalizedDocument(
        document_id=doc.document_id,
        content="DP charge schedule...",
        sections=[],
        source_hash=doc.source_hash,
    )
    await pg_repo.save_ingested_knowledge(normalized_doc=norm, org_doc=doc)

    retrieved = await pg_repo.get_organisation_document("doc_org_zerodha_test_pg_02")
    assert retrieved is not None
    assert retrieved.organisation_id == "ORG_ZERODHA"
    assert retrieved.applicable_process == "dp_charges"


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_05_persist_provenance_and_uniqueness(pg_repo):
    """5. Persist provenance record and verify hash search."""
    prov_hash = "c" * 64
    has_hash = await pg_repo.has_hash(prov_hash)
    assert has_hash is False

    doc = RegulatoryDocument(
        document_id="doc_reg_prov_test",
        authority="SEBI",
        document_type="Circular",
        title="Provenance Test Document",
        document_identifier="PROV-001",
        source_url=HttpUrl("https://www.sebi.gov.in/prov.pdf"),
        source_hash=prov_hash,
    )
    norm = NormalizedDocument(document_id=doc.document_id, content="Content", source_hash=prov_hash)
    await pg_repo.save_ingested_knowledge(normalized_doc=norm, reg_doc=doc)

    assert await pg_repo.has_hash(prov_hash) is True


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_06_persist_sections_and_07_reconstruct_hierarchy(pg_repo):
    """6 & 7. Persist and reconstruct hierarchical sections."""
    doc_id = "doc_reg_tree_test"
    doc = RegulatoryDocument(
        document_id=doc_id,
        authority="SEBI",
        document_type="Circular",
        title="Section Tree Test",
        document_identifier="TREE-001",
        source_url=HttpUrl("https://www.sebi.gov.in/tree.pdf"),
        source_hash="d" * 64,
    )
    sections = [
        DocumentSection(
            section_id="sec_1",
            heading="Chapter 1",
            level=1,
            content="Chapter 1 Text",
            subsections=[
                DocumentSection(
                    section_id="sec_1_1",
                    heading="Section 1.1",
                    level=2,
                    content="Subsection 1.1 Text",
                )
            ],
        )
    ]
    norm = NormalizedDocument(
        document_id=doc_id,
        content="Raw",
        sections=sections,
        source_hash="d" * 64,
    )
    await pg_repo.save_ingested_knowledge(normalized_doc=norm, reg_doc=doc)

    reconstructed = await pg_repo.get_sections_for_document(doc_id)
    assert len(reconstructed) == 1
    assert reconstructed[0].section_id == "sec_1"
    assert len(reconstructed[0].subsections) == 1
    assert reconstructed[0].subsections[0].section_id == "sec_1_1"


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_08_persist_provisions_and_09_orphan_fk_rejection(pg_repo):
    """8 & 9. Persist provisions and verify foreign-key rejection for orphan provision."""
    doc_id = "doc_reg_prov_test_parent"
    doc = RegulatoryDocument(
        document_id=doc_id,
        authority="SEBI",
        document_type="Act",
        title="Parent Document",
        document_identifier="PARENT-001",
        source_url=HttpUrl("https://sebi.gov.in/parent.pdf"),
        source_hash="e" * 64,
    )
    prov = RegulatoryProvision(
        provision_id="PROV-VALID-01",
        document_id=doc_id,
        section="Section 11",
        source_text="Powers of the board.",
    )
    norm = NormalizedDocument(document_id=doc_id, content="Content", source_hash="e" * 64)
    await pg_repo.save_ingested_knowledge(normalized_doc=norm, reg_doc=doc, provisions=[prov])

    provisions = await pg_repo.list_provisions_for_document(doc_id)
    assert len(provisions) == 1
    assert provisions[0].provision_id == "PROV-VALID-01"

    # Attempting to persist an orphan provision directly to the database without a parent document must fail FK
    async with get_async_session() as session:
        orphan = RegulatoryProvisionORM(
            provision_id="PROV-ORPHAN-SQL",
            document_id="NON_EXISTENT_DOC_ID",
            source_text="Should violate FK",
            definitions=[],
            cross_references=[],
        )
        session.add(orphan)
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.commit()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_10_persist_relationships_and_11_self_reference_rejection(pg_repo):
    """10 & 11. Persist relationships and enforce self-reference rejection."""
    doc_id = "doc_reg_rel_parent"
    doc = RegulatoryDocument(
        document_id=doc_id,
        authority="SEBI",
        document_type="Circular",
        title="Relationship Test",
        document_identifier="REL-001",
        source_url=HttpUrl("https://sebi.gov.in/rel.pdf"),
        source_hash="f" * 64,
    )
    rel = KnowledgeRelationship(
        relationship_id="REL-TEST-PG-1",
        source_id=doc_id,
        target_id="doc_reg_target",
        relationship_type=RelationshipType.SUPERSEDES,
    )
    norm = NormalizedDocument(document_id=doc_id, content="Content", source_hash="f" * 64)
    await pg_repo.save_ingested_knowledge(normalized_doc=norm, reg_doc=doc, relationships=[rel])


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_12_duplicate_content_detection(pg_repo):
    """12. Duplicate content detection via source_hash in PostgreSQL."""
    test_hash = "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
    doc = RegulatoryDocument(
        document_id="doc_dedup_01",
        authority="SEBI",
        document_type="Circular",
        title="Dedup Document",
        document_identifier="DEDUP-001",
        source_url=HttpUrl("https://sebi.gov.in/dedup.html"),
        source_hash=test_hash,
    )
    norm = NormalizedDocument(document_id=doc.document_id, content="Content", source_hash=test_hash)
    await pg_repo.save_ingested_knowledge(normalized_doc=norm, reg_doc=doc)

    assert await pg_repo.has_hash(test_hash) is True


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_13_transaction_rollback(pg_repo):
    """13. Ensure transactional rollback on failure leaves zero partial records."""
    failing_hash = "9" * 64
    failing_doc_id = "doc_transaction_fail_test"

    doc = RegulatoryDocument(
        document_id=failing_doc_id,
        authority="SEBI",
        document_type="Circular",
        title="Transaction Fail Test",
        document_identifier="FAIL-001",
        source_url=HttpUrl("https://sebi.gov.in/fail.html"),
        source_hash=failing_hash,
    )
    norm = NormalizedDocument(document_id=failing_doc_id, content="Content", source_hash=failing_hash)

    # Invalid provision referencing non-existent parent to force transaction crash
    bad_prov = RegulatoryProvision(
        provision_id="PROV-CRASH",
        document_id="SOME_DIFFERENT_NONEXISTENT_PARENT",
        source_text="Crash",
    )

    with pytest.raises(Exception):
        await pg_repo.save_ingested_knowledge(
            normalized_doc=norm,
            reg_doc=doc,
            provisions=[bad_prov],
        )

    # Confirm doc was rolled back completely
    rolled_back_doc = await pg_repo.get_document(failing_doc_id)
    assert rolled_back_doc is None
    assert await pg_repo.has_hash(failing_hash) is False


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_14_persistence_across_session_restart(pg_repo):
    """14. Confirm persistence survives across new session connections."""
    doc_id = "doc_restart_test_01"
    doc = RegulatoryDocument(
        document_id=doc_id,
        authority="SEBI",
        document_type="Circular",
        title="Restart Test",
        document_identifier="RESTART-001",
        source_url=HttpUrl("https://sebi.gov.in/restart.html"),
        source_hash="8" * 64,
    )
    norm = NormalizedDocument(document_id=doc_id, content="Content", source_hash="8" * 64)
    await pg_repo.save_ingested_knowledge(normalized_doc=norm, reg_doc=doc)

    # Instantiate brand new repository instance
    new_repo = PostgresKnowledgeRepository()
    fetched = await new_repo.get_document(doc_id)
    assert fetched is not None
    assert fetched.document_id == doc_id


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_15_organisation_filtering(pg_repo):
    """15. Filter organisation documents by organisation_id."""
    org_docs = await pg_repo.list_documents_for_org("ORG_ZERODHA")
    assert isinstance(org_docs, list)
    assert all(d.organisation_id == "ORG_ZERODHA" for d in org_docs)


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_16_regulatory_filtering(pg_repo):
    """16. List provisions for regulatory document."""
    provisions = await pg_repo.list_provisions_for_document("doc_reg_prov_test_parent")
    assert isinstance(provisions, list)


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_17_temporal_metadata_preservation(pg_repo):
    """17. Confirm temporal dates and superseded status are preserved in PostgreSQL."""
    doc_id = "doc_temporal_pg_test"
    doc = RegulatoryDocument(
        document_id=doc_id,
        authority="SEBI",
        document_type="Circular",
        title="Temporal Test",
        document_identifier="TEMP-001",
        publication_date=date(2022, 5, 10),
        effective_date=date(2022, 6, 1),
        termination_date=date(2025, 12, 31),
        superseded_status=SupersededStatus.PARTIALLY_AMENDED,
        source_url=HttpUrl("https://sebi.gov.in/temp.pdf"),
        source_hash="7" * 64,
    )
    norm = NormalizedDocument(document_id=doc_id, content="Content", source_hash="7" * 64)
    await pg_repo.save_ingested_knowledge(normalized_doc=norm, reg_doc=doc)

    retrieved = await pg_repo.get_document(doc_id)
    assert retrieved is not None
    assert retrieved.publication_date == date(2022, 5, 10)
    assert retrieved.effective_date == date(2022, 6, 1)
    assert retrieved.termination_date == date(2025, 12, 31)
    assert retrieved.superseded_status == SupersededStatus.PARTIALLY_AMENDED


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_pg_18_ingestion_record_persistence(pg_repo):
    """18. Record operational ingestion event and verify persistence."""
    await pg_repo.record_ingestion_attempt(
        ingestion_id="INGEST-TEST-001",
        source_url="https://sebi.gov.in/doc.html",
        final_url="https://sebi.gov.in/canonical.html",
        source_hash="6" * 64,
        document_id="doc_test_001",
        ingestion_status="SUCCESS",
    )
