"""PostgreSQL implementation of SANGYAN knowledge repository contracts.

Implements:
- RegulatoryKnowledgeRepository
- OrganisationKnowledgeRepository

Guarantees:
- Strict transactional atomicity: all entities (document, provenance, sections, provisions)
  are persisted in a single transaction or rolled back completely.
- Content hash deduplication backed by relational database indexing and constraints.
- Section hierarchy preservation with relational parent-child keys.
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai.app.db.mappers import (
    flatten_section_tree,
    knowledge_provision_from_orm,
    knowledge_provision_to_orm,
    organisation_doc_from_orm,
    organisation_doc_to_orm,
    organisation_provision_from_orm,
    organisation_provision_to_orm,
    provenance_to_orm,
    reconstruct_section_tree,
    regulatory_doc_from_orm,
    regulatory_doc_to_orm,
    regulatory_provision_from_orm,
    regulatory_provision_to_orm,
    relationship_to_orm,
)
from ai.app.db.models import (
    DocumentSectionORM,
    IngestionRecordORM,
    KnowledgeProvisionORM,
    KnowledgeRelationshipORM,
    OrganisationDocumentORM,
    OrganisationProvisionORM,
    ProvenanceORM,
    RegulatoryDocumentORM,
    RegulatoryProvisionORM,
)
from ai.app.db.session import get_async_engine
from ai.app.knowledge.documents import (
    DocumentSection,
    NormalizedDocument,
    OrganisationDocument,
    RegulatoryDocument,
)
from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.provisions import (
    OrganisationProvision,
    Provision,
    RegulatoryProvision,
)
from ai.app.knowledge.relationships import KnowledgeRelationship
from ai.app.organisation.contracts import OrganisationKnowledgeRepository
from ai.app.regulatory.contracts import RegulatoryKnowledgeRepository


class PostgresKnowledgeRepository(RegulatoryKnowledgeRepository, OrganisationKnowledgeRepository):
    """PostgreSQL knowledge repository implementing SANGYAN repository contracts."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            engine = get_async_engine()
            self._session_factory = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )

    async def get_document(self, document_id: str) -> RegulatoryDocument | None:
        """Fetch regulatory document by ID."""
        async with self._session_factory() as session:
            stmt = select(RegulatoryDocumentORM).where(RegulatoryDocumentORM.document_id == document_id)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()
            if orm:
                return regulatory_doc_from_orm(orm)
            return None

    async def get_organisation_document(self, document_id: str) -> OrganisationDocument | None:
        """Fetch organisation document by ID."""
        async with self._session_factory() as session:
            stmt = select(OrganisationDocumentORM).where(OrganisationDocumentORM.document_id == document_id)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()
            if orm:
                return organisation_doc_from_orm(orm)
            return None

    async def get_provision(self, provision_id: str) -> RegulatoryProvision | OrganisationProvision | None:
        """Fetch provision by ID from regulatory or organisation provisions."""
        async with self._session_factory() as session:
            reg_stmt = select(RegulatoryProvisionORM).where(RegulatoryProvisionORM.provision_id == provision_id)
            reg_res = await session.execute(reg_stmt)
            reg_orm = reg_res.scalar_one_or_none()
            if reg_orm:
                return regulatory_provision_from_orm(reg_orm)

            org_stmt = select(OrganisationProvisionORM).where(OrganisationProvisionORM.provision_id == provision_id)
            org_res = await session.execute(org_stmt)
            org_orm = org_res.scalar_one_or_none()
            if org_orm:
                return organisation_provision_from_orm(org_orm)

            return None

    async def list_provisions_for_document(self, document_id: str) -> list[RegulatoryProvision]:
        """Fetch all provisions belonging to a regulatory document."""
        async with self._session_factory() as session:
            stmt = (
                select(RegulatoryProvisionORM)
                .where(RegulatoryProvisionORM.document_id == document_id)
            )
            result = await session.execute(stmt)
            orms = result.scalars().all()
            return [regulatory_provision_from_orm(o) for o in orms]

    async def list_documents_for_org(self, organisation_id: str) -> list[OrganisationDocument]:
        """Fetch all organisation documents for a given intermediary."""
        async with self._session_factory() as session:
            stmt = (
                select(OrganisationDocumentORM)
                .where(OrganisationDocumentORM.organisation_id == organisation_id)
            )
            result = await session.execute(stmt)
            orms = result.scalars().all()
            return [organisation_doc_from_orm(o) for o in orms]

    async def has_hash(self, source_hash: str) -> bool:
        """Check if source hash already exists in provenance or documents."""
        async with self._session_factory() as session:
            stmt = select(ProvenanceORM.id).where(ProvenanceORM.source_hash == source_hash).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def get_sections_for_document(self, document_id: str) -> list[DocumentSection]:
        """Retrieve hierarchical section tree for a document."""
        async with self._session_factory() as session:
            stmt = (
                select(DocumentSectionORM)
                .where(DocumentSectionORM.document_id == document_id)
                .order_by(DocumentSectionORM.order_index)
            )
            result = await session.execute(stmt)
            orms = list(result.scalars().all())
            return reconstruct_section_tree(orms)

    async def save_ingested_knowledge(
        self,
        normalized_doc: NormalizedDocument,
        reg_doc: RegulatoryDocument | None = None,
        org_doc: OrganisationDocument | None = None,
        provenance: Provenance | None = None,
        provisions: Sequence[RegulatoryProvision | OrganisationProvision] | None = None,
        relationships: Sequence[KnowledgeRelationship] | None = None,
    ) -> None:
        """Atomically persist a complete ingested knowledge bundle in a single transaction.
        
        Guarantees that documents, sections, provisions, and provenance are all written or all rolled back.
        """
        async with self._session_factory() as session:
            async with session.begin():
                doc_id = normalized_doc.document_id

                # 1. Persist parent document row
                if reg_doc:
                    session.add(regulatory_doc_to_orm(reg_doc))
                elif org_doc:
                    session.add(organisation_doc_to_orm(org_doc))

                # 2. Persist provenance record
                prov_to_save = provenance or (
                    Provenance(
                        source_url=reg_doc.source_url if reg_doc else org_doc.source_url, # type: ignore
                        document_id=doc_id,
                        source_hash=normalized_doc.source_hash,
                        source_class=reg_doc.source_class if reg_doc else org_doc.source_class, # type: ignore
                    )
                    if (reg_doc or org_doc)
                    else None
                )
                if prov_to_save:
                    session.add(provenance_to_orm(prov_to_save))

                # 3. Persist hierarchical document sections
                if normalized_doc.sections:
                    flat_items = flatten_section_tree(doc_id, normalized_doc.sections)
                    key_to_persisted_id: dict[str, int] = {}

                    # First pass: persist roots and get IDs
                    for orm_sec, parent_key in flat_items:
                        if parent_key is None:
                            session.add(orm_sec)
                            await session.flush()
                            key_to_persisted_id[orm_sec.section_key] = orm_sec.id

                    # Second pass: persist child sections linking to parent IDs
                    for orm_sec, parent_key in flat_items:
                        if parent_key is not None:
                            orm_sec.parent_section_id = key_to_persisted_id.get(parent_key)
                            session.add(orm_sec)
                            await session.flush()
                            key_to_persisted_id[orm_sec.section_key] = orm_sec.id

                # 4. Persist provisions
                if provisions:
                    for p in provisions:
                        if isinstance(p, RegulatoryProvision):
                            session.add(regulatory_provision_to_orm(p))
                        elif isinstance(p, OrganisationProvision):
                            session.add(organisation_provision_to_orm(p))

                # 5. Persist relationships
                if relationships:
                    for rel in relationships:
                        session.add(relationship_to_orm(rel))

    async def record_ingestion_attempt(
        self,
        ingestion_id: str,
        source_url: str,
        source_hash: str,
        ingestion_status: str,
        final_url: str | None = None,
        document_id: str | None = None,
        retrieved_at: datetime | None = None,
        error_stage: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Write an operational ingestion record."""
        async with self._session_factory() as session:
            async with session.begin():
                record = IngestionRecordORM(
                    ingestion_id=ingestion_id,
                    source_url=source_url,
                    final_url=final_url,
                    source_hash=source_hash,
                    document_id=document_id,
                    ingestion_status=ingestion_status,
                    retrieved_at=retrieved_at or datetime.now(timezone.utc),
                    error_stage=error_stage,
                    error_message=error_message,
                )
                session.add(record)

    async def save_provisions(self, provisions: Sequence[Provision]) -> int:
        """Atomically persist or update atomic knowledge provisions."""
        if not provisions:
            return 0
        async with self._session_factory() as session:
            async with session.begin():
                saved_count = 0
                for prov in provisions:
                    existing = await session.get(KnowledgeProvisionORM, prov.provision_id)
                    if existing is None:
                        session.add(knowledge_provision_to_orm(prov))
                        saved_count += 1
                return saved_count

    async def get_knowledge_provision(self, provision_id: str) -> Provision | None:
        """Fetch an atomic knowledge provision by ID."""
        async with self._session_factory() as session:
            orm = await session.get(KnowledgeProvisionORM, provision_id)
            if orm:
                return knowledge_provision_from_orm(orm)
            return None

    async def list_provisions_by_document(self, document_id: str) -> list[Provision]:
        """Fetch all atomic knowledge provisions belonging to a document."""
        async with self._session_factory() as session:
            stmt = (
                select(KnowledgeProvisionORM)
                .where(KnowledgeProvisionORM.document_id == document_id)
            )
            res = await session.execute(stmt)
            return [knowledge_provision_from_orm(o) for o in res.scalars().all()]

    async def list_all_knowledge_provisions(self) -> list[Provision]:
        """Fetch all atomic knowledge provisions currently persisted."""
        async with self._session_factory() as session:
            stmt = select(KnowledgeProvisionORM)
            res = await session.execute(stmt)
            return [knowledge_provision_from_orm(o) for o in res.scalars().all()]

    async def list_all_sections(self) -> list[dict[str, Any]]:
        """Retrieve all persisted document sections."""
        async with self._session_factory() as session:
            stmt = (
                select(
                    DocumentSectionORM.id,
                    DocumentSectionORM.document_id,
                    DocumentSectionORM.section_key,
                    DocumentSectionORM.parent_section_id,
                    DocumentSectionORM.heading,
                    DocumentSectionORM.level,
                    DocumentSectionORM.order_index,
                    DocumentSectionORM.content,
                )
                .order_by(DocumentSectionORM.document_id, DocumentSectionORM.order_index)
            )
            res = await session.execute(stmt)
            return [
                {
                    "id": r[0],
                    "document_id": r[1],
                    "section_key": r[2],
                    "parent_section_id": r[3],
                    "heading": r[4],
                    "level": r[5],
                    "order_index": r[6],
                    "content": r[7],
                }
                for r in res.all()
            ]

