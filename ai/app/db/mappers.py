"""Bidirectional mapping between Pydantic canonical domain models and SQLAlchemy ORM entities.

Ensures strict round-trip invariant:
Pydantic model → ORM entity → Pydantic model preserves all semantically important fields.
"""

from typing import Any
from pydantic import HttpUrl

from ai.app.db.models import (
    DocumentSectionORM,
    KnowledgeProvisionORM,
    KnowledgeRelationshipORM,
    OrganisationDocumentORM,
    OrganisationProvisionORM,
    ProvenanceORM,
    RegulatoryDocumentORM,
    RegulatoryProvisionORM,
)
from ai.app.knowledge.documents import (
    DocumentSection,
    OrganisationDocument,
    RegulatoryDocument,
)
from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.provisions import OrganisationProvision, RegulatoryProvision
from ai.app.knowledge.relationships import KnowledgeRelationship, RelationshipType
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import SupersededStatus, TemporalScope


# =====================================================================
# Regulatory Document Mappers
# =====================================================================

def regulatory_doc_to_orm(doc: RegulatoryDocument) -> RegulatoryDocumentORM:
    return RegulatoryDocumentORM(
        document_id=doc.document_id,
        authority=doc.authority,
        jurisdiction=doc.jurisdiction,
        document_type=doc.document_type,
        title=doc.title,
        document_identifier=doc.document_identifier,
        publication_date=doc.publication_date,
        effective_date=doc.effective_date,
        termination_date=doc.termination_date,
        superseded_status=doc.superseded_status.value,
        source_url=str(doc.source_url),
        source_hash=doc.source_hash,
        retrieved_at=doc.retrieved_at,
        source_class=doc.source_class.value,
    )


def regulatory_doc_from_orm(orm: RegulatoryDocumentORM) -> RegulatoryDocument:
    return RegulatoryDocument(
        document_id=orm.document_id,
        authority=orm.authority,
        jurisdiction=orm.jurisdiction,
        document_type=orm.document_type,
        title=orm.title,
        document_identifier=orm.document_identifier,
        publication_date=orm.publication_date,
        effective_date=orm.effective_date,
        termination_date=orm.termination_date,
        superseded_status=SupersededStatus(orm.superseded_status),
        source_url=HttpUrl(orm.source_url),
        source_hash=orm.source_hash,
        retrieved_at=orm.retrieved_at,
        source_class=SourceClass(orm.source_class),
    )


# =====================================================================
# Organisation Document Mappers
# =====================================================================

def organisation_doc_to_orm(doc: OrganisationDocument) -> OrganisationDocumentORM:
    return OrganisationDocumentORM(
        document_id=doc.document_id,
        organisation_id=doc.organisation_id,
        source_class=doc.source_class.value,
        document_type=doc.document_type,
        title=doc.title,
        document_identifier=doc.document_identifier,
        publication_date=doc.publication_date,
        effective_date=doc.effective_date,
        termination_date=doc.termination_date,
        superseded_status=doc.superseded_status.value,
        source_url=str(doc.source_url),
        source_hash=doc.source_hash,
        retrieved_at=doc.retrieved_at,
        organisation_name=doc.organisation_name,
        applicable_process=doc.applicable_process,
        topic=doc.topic,
    )


def organisation_doc_from_orm(orm: OrganisationDocumentORM) -> OrganisationDocument:
    return OrganisationDocument(
        document_id=orm.document_id,
        organisation_id=orm.organisation_id,
        source_class=SourceClass(orm.source_class),
        document_type=orm.document_type,
        title=orm.title,
        document_identifier=orm.document_identifier,
        publication_date=orm.publication_date,
        effective_date=orm.effective_date,
        termination_date=orm.termination_date,
        superseded_status=SupersededStatus(orm.superseded_status),
        source_url=HttpUrl(orm.source_url),
        source_hash=orm.source_hash,
        retrieved_at=orm.retrieved_at,
        organisation_name=orm.organisation_name,
        applicable_process=orm.applicable_process,
        topic=orm.topic,
    )


# =====================================================================
# Provenance Mappers
# =====================================================================

def provenance_to_orm(prov: Provenance) -> ProvenanceORM:
    return ProvenanceORM(
        document_id=prov.document_id,
        source_url=str(prov.source_url),
        source_hash=prov.source_hash,
        retrieved_at=prov.retrieved_at,
        source_class=prov.source_class.value,
        extractor_version=prov.extractor_version,
    )


def provenance_from_orm(orm: ProvenanceORM) -> Provenance:
    return Provenance(
        source_url=HttpUrl(orm.source_url),
        document_id=orm.document_id,
        source_hash=orm.source_hash,
        retrieved_at=orm.retrieved_at,
        source_class=SourceClass(orm.source_class),
        extractor_version=orm.extractor_version,
    )


# =====================================================================
# Document Section Tree Mappers
# =====================================================================

def flatten_section_tree(
    document_id: str,
    sections: list[DocumentSection],
    parent_key: str | None = None,
    order_start: int = 0,
) -> list[tuple[DocumentSectionORM, str | None]]:
    """Flatten hierarchical DocumentSection tree into ORM entities while preserving parent references."""
    items: list[tuple[DocumentSectionORM, str | None]] = []
    current_order = order_start

    for sec in sections:
        orm = DocumentSectionORM(
            document_id=document_id,
            section_key=sec.section_id,
            heading=sec.heading,
            level=sec.level,
            order_index=current_order,
            content=sec.content,
        )
        items.append((orm, parent_key))
        current_order += 1

        if sec.subsections:
            sub_items = flatten_section_tree(
                document_id=document_id,
                sections=sec.subsections,
                parent_key=sec.section_id,
                order_start=current_order,
            )
            items.extend(sub_items)
            current_order += len(sub_items)

    return items


def reconstruct_section_tree(orm_sections: list[DocumentSectionORM]) -> list[DocumentSection]:
    """Reconstruct nested DocumentSection hierarchy from flat ordered ORM records."""
    if not orm_sections:
        return []

    # Map by id -> DocumentSection and list of child IDs
    id_to_section: dict[int, DocumentSection] = {}
    id_to_parent_id: dict[int, int | None] = {}
    ordered_roots: list[int] = []

    for s in sorted(orm_sections, key=lambda x: x.order_index):
        sec = DocumentSection(
            section_id=s.section_key,
            heading=s.heading,
            level=s.level,
            content=s.content,
            subsections=[],
        )
        id_to_section[s.id] = sec
        id_to_parent_id[s.id] = s.parent_section_id
        if s.parent_section_id is None:
            ordered_roots.append(s.id)

    # Attach children to parents
    for s_id, parent_id in id_to_parent_id.items():
        if parent_id is not None and parent_id in id_to_section:
            id_to_section[parent_id].subsections.append(id_to_section[s_id])

    return [id_to_section[r_id] for r_id in ordered_roots]


# =====================================================================
# Provisions Mappers
# =====================================================================

def regulatory_provision_to_orm(prov: RegulatoryProvision) -> RegulatoryProvisionORM:
    return RegulatoryProvisionORM(
        provision_id=prov.provision_id,
        document_id=prov.document_id,
        section=prov.section,
        clause=prov.clause,
        paragraph=prov.paragraph,
        source_text=prov.source_text,
        definitions=prov.definitions,
        cross_references=prov.cross_references,
        publication_date=prov.temporal_scope.publication_date,
        effective_date=prov.temporal_scope.effective_date,
        termination_date=prov.temporal_scope.termination_date,
        superseded_status=prov.temporal_scope.superseded_status.value,
    )


def regulatory_provision_from_orm(orm: RegulatoryProvisionORM) -> RegulatoryProvision:
    return RegulatoryProvision(
        provision_id=orm.provision_id,
        document_id=orm.document_id,
        section=orm.section,
        clause=orm.clause,
        paragraph=orm.paragraph,
        source_text=orm.source_text,
        definitions=list(orm.definitions or []),
        cross_references=list(orm.cross_references or []),
        temporal_scope=TemporalScope(
            publication_date=orm.publication_date,
            effective_date=orm.effective_date,
            termination_date=orm.termination_date,
            superseded_status=SupersededStatus(orm.superseded_status),
        ),
    )


def organisation_provision_to_orm(prov: OrganisationProvision) -> OrganisationProvisionORM:
    return OrganisationProvisionORM(
        provision_id=prov.provision_id,
        document_id=prov.document_id,
        organisation_id=prov.organisation_id,
        section=prov.section,
        clause=prov.clause,
        source_text=prov.source_text,
        applicable_process=prov.applicable_process,
        publication_date=prov.temporal_scope.publication_date,
        effective_date=prov.temporal_scope.effective_date,
        termination_date=prov.temporal_scope.termination_date,
        superseded_status=prov.temporal_scope.superseded_status.value,
    )


def organisation_provision_from_orm(orm: OrganisationProvisionORM) -> OrganisationProvision:
    return OrganisationProvision(
        provision_id=orm.provision_id,
        document_id=orm.document_id,
        organisation_id=orm.organisation_id,
        section=orm.section,
        clause=orm.clause,
        source_text=orm.source_text,
        applicable_process=orm.applicable_process,
        temporal_scope=TemporalScope(
            publication_date=orm.publication_date,
            effective_date=orm.effective_date,
            termination_date=orm.termination_date,
            superseded_status=SupersededStatus(orm.superseded_status),
        ),
    )


# =====================================================================
# Knowledge Relationships Mappers
# =====================================================================

def relationship_to_orm(rel: KnowledgeRelationship) -> KnowledgeRelationshipORM:
    return KnowledgeRelationshipORM(
        relationship_id=rel.relationship_id,
        source_id=rel.source_id,
        target_id=rel.target_id,
        relationship_type=rel.relationship_type.value,
        description=rel.description,
        effective_date=rel.effective_date,
        metadata_json=rel.metadata,
    )


def relationship_from_orm(orm: KnowledgeRelationshipORM) -> KnowledgeRelationship:
    return KnowledgeRelationship(
        relationship_id=orm.relationship_id,
        source_id=orm.source_id,
        target_id=orm.target_id,
        relationship_type=RelationshipType(orm.relationship_type),
        description=orm.description,
        effective_date=orm.effective_date,
        metadata=dict(orm.metadata_json or {}),
    )


# =====================================================================
# Atomic Knowledge Provision Mappers
# =====================================================================

def knowledge_provision_to_orm(prov: "Provision") -> KnowledgeProvisionORM:
    from datetime import datetime, timezone
    return KnowledgeProvisionORM(
        provision_id=prov.provision_id,
        document_id=prov.document_id,
        section_id=prov.section_id,
        parent_provision_id=prov.parent_provision_id,
        provision_type=prov.provision_type.value,
        source_text=prov.source_text,
        source_start=prov.source_start,
        source_end=prov.source_end,
        title=prov.title,
        section_reference=prov.section_reference,
        clause_reference=prov.clause_reference,
        authority=prov.authority,
        organisation_id=prov.organisation_id,
        source_class=prov.source_class.value,
        topic=list(prov.topic or []),
        process=prov.process,
        applicable_entity=list(prov.applicable_entity or []),
        effective_date=prov.effective_date,
        termination_date=prov.termination_date,
        temporal_status=prov.temporal_status.value,
        conditions_json=[c.model_dump() for c in prov.conditions],
        exceptions_json=[e.model_dump() for e in prov.exceptions],
        procedures_json=[p.model_dump() for p in prov.procedures],
        timelines_json=[t.model_dump() for t in prov.timelines],
        fees_json=[f.model_dump() for f in prov.fees],
        definitions_json=[d.model_dump() for d in prov.definitions],
        cross_references_json=[cr.model_dump() for cr in prov.cross_references],
        provenance_json=prov.provenance.model_dump(mode="json") if prov.provenance else {},
        extraction_metadata=dict(prov.extraction_metadata or {}),
        created_at=datetime.now(timezone.utc),
    )


def knowledge_provision_from_orm(orm: KnowledgeProvisionORM) -> "Provision":
    from ai.app.knowledge.provisions import (
        Condition,
        CrossReference,
        Definition,
        ExceptionClause,
        FeeOrCharge,
        ProcedureStep,
        Provision,
        ProvisionType,
        Timeline,
    )
    from ai.app.knowledge.provenance import Provenance
    from ai.app.knowledge.source_classes import SourceClass
    from ai.app.knowledge.temporal import SupersededStatus

    prov_record = None
    if orm.provenance_json and isinstance(orm.provenance_json, dict) and "source_url" in orm.provenance_json:
        try:
            prov_record = Provenance.model_validate(orm.provenance_json)
        except Exception:
            prov_record = None

    return Provision(
        provision_id=orm.provision_id,
        document_id=orm.document_id,
        section_id=orm.section_id,
        parent_provision_id=orm.parent_provision_id,
        provision_type=ProvisionType(orm.provision_type),
        source_text=orm.source_text,
        source_start=orm.source_start,
        source_end=orm.source_end,
        title=orm.title,
        section_reference=orm.section_reference,
        clause_reference=orm.clause_reference,
        authority=orm.authority,
        organisation_id=orm.organisation_id,
        source_class=SourceClass(orm.source_class),
        topic=list(orm.topic or []),
        process=orm.process,
        applicable_entity=list(orm.applicable_entity or []),
        effective_date=orm.effective_date,
        termination_date=orm.termination_date,
        temporal_status=SupersededStatus(orm.temporal_status),
        provenance=prov_record,
        conditions=[Condition.model_validate(c) for c in (orm.conditions_json or [])],
        exceptions=[ExceptionClause.model_validate(e) for e in (orm.exceptions_json or [])],
        procedures=[ProcedureStep.model_validate(p) for p in (orm.procedures_json or [])],
        timelines=[Timeline.model_validate(t) for t in (orm.timelines_json or [])],
        fees=[FeeOrCharge.model_validate(f) for f in (orm.fees_json or [])],
        definitions=[Definition.model_validate(d) for d in (orm.definitions_json or [])],
        cross_references=[CrossReference.model_validate(cr) for cr in (orm.cross_references_json or [])],
        extraction_metadata=dict(orm.extraction_metadata or {}),
    )

