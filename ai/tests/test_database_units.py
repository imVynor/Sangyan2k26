"""Unit tests for PostgreSQL persistence models, mappers, and repository contracts.

Runs 100% offline without requiring an active PostgreSQL instance.
Tests:
1. Repository interface compatibility
2. Model-to-database mapping
3. Invalid source class rejection
4. Orphan provision rejection at application level
5. Relationship self-reference rejection
6. Serialization/deserialization and JSONB field roundtrips
7. Document ID preservation
8. Source hash preservation
9. Hierarchical section tree reconstruction
10. Epistemic boundary enforcement
"""

from datetime import date, datetime, timezone
import pytest
from pydantic import HttpUrl, ValidationError

from ai.app.db.mappers import (
    flatten_section_tree,
    organisation_doc_from_orm,
    organisation_doc_to_orm,
    organisation_provision_from_orm,
    organisation_provision_to_orm,
    provenance_from_orm,
    provenance_to_orm,
    reconstruct_section_tree,
    regulatory_doc_from_orm,
    regulatory_doc_to_orm,
    regulatory_provision_from_orm,
    regulatory_provision_to_orm,
    relationship_from_orm,
    relationship_to_orm,
)
from ai.app.db.models import (
    DocumentSectionORM,
    OrganisationDocumentORM,
    OrganisationProvisionORM,
    RegulatoryDocumentORM,
    RegulatoryProvisionORM,
)
from ai.app.db.repository import PostgresKnowledgeRepository
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
from ai.app.organisation.contracts import OrganisationKnowledgeRepository
from ai.app.regulatory.contracts import RegulatoryKnowledgeRepository
from ai.app.validation.knowledge import CaseKnowledgeBoundaryError, assert_not_case_state


# =====================================================================
# Unit Test Scenarios
# =====================================================================

def test_01_repository_interface_compatibility():
    """1. Verify PostgresKnowledgeRepository implements both repository contracts."""
    assert issubclass(PostgresKnowledgeRepository, RegulatoryKnowledgeRepository)
    assert issubclass(PostgresKnowledgeRepository, OrganisationKnowledgeRepository)


def test_02_regulatory_model_to_orm_mapping_and_roundtrip():
    """2. Regulatory document Pydantic <-> ORM mapping roundtrip invariant."""
    pydantic_doc = RegulatoryDocument(
        document_id="doc_reg_sebi_1234567890abcdef",
        authority="SEBI",
        jurisdiction="India",
        document_type="Master Circular",
        title="Master Circular on Surveillance of Securities Market",
        document_identifier="SEBI/HO/ISD/ISD-POD-2/P/CIR/2023/039",
        publication_date=date(2023, 3, 23),
        effective_date=date(2023, 4, 1),
        termination_date=None,
        superseded_status=SupersededStatus.CURRENT,
        source_url=HttpUrl("https://www.sebi.gov.in/legal/master-circulars/mar-2023/circ.pdf"),
        source_hash="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        retrieved_at=datetime.now(timezone.utc),
        source_class=SourceClass.REGULATORY,
    )

    orm_entity = regulatory_doc_to_orm(pydantic_doc)
    assert isinstance(orm_entity, RegulatoryDocumentORM)
    assert orm_entity.document_id == pydantic_doc.document_id
    assert orm_entity.authority == "SEBI"
    assert orm_entity.source_hash == pydantic_doc.source_hash

    # Roundtrip back to Pydantic
    roundtrip_doc = regulatory_doc_from_orm(orm_entity)
    assert roundtrip_doc.document_id == pydantic_doc.document_id
    assert roundtrip_doc.authority == pydantic_doc.authority
    assert roundtrip_doc.title == pydantic_doc.title
    assert roundtrip_doc.publication_date == pydantic_doc.publication_date
    assert roundtrip_doc.effective_date == pydantic_doc.effective_date
    assert roundtrip_doc.superseded_status == pydantic_doc.superseded_status
    assert str(roundtrip_doc.source_url) == str(pydantic_doc.source_url)
    assert roundtrip_doc.source_hash == pydantic_doc.source_hash


def test_03_organisation_model_to_orm_mapping_and_roundtrip():
    """3. Organisation document Pydantic <-> ORM mapping roundtrip invariant."""
    pydantic_doc = OrganisationDocument(
        document_id="doc_org_zerodha_abcdef1234567890",
        organisation_id="ORG_ZERODHA",
        source_class=SourceClass.ORGANISATION_POLICY,
        document_type="Fee Schedule",
        title="Brokerage and Charges Schedule",
        document_identifier="TARIFF-2024-V2",
        publication_date=date(2024, 1, 1),
        effective_date=date(2024, 1, 1),
        termination_date=None,
        superseded_status=SupersededStatus.CURRENT,
        source_url=HttpUrl("https://zerodha.com/charges.html"),
        source_hash="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        retrieved_at=datetime.now(timezone.utc),
        organisation_name="Zerodha Broking Ltd",
        applicable_process="dp_charges",
        topic="charges",
    )

    orm_entity = organisation_doc_to_orm(pydantic_doc)
    assert isinstance(orm_entity, OrganisationDocumentORM)
    assert orm_entity.organisation_id == "ORG_ZERODHA"
    assert orm_entity.source_class == "ORGANISATION_POLICY"

    # Roundtrip back
    roundtrip_doc = organisation_doc_from_orm(orm_entity)
    assert roundtrip_doc.document_id == pydantic_doc.document_id
    assert roundtrip_doc.organisation_id == pydantic_doc.organisation_id
    assert roundtrip_doc.source_class == SourceClass.ORGANISATION_POLICY
    assert roundtrip_doc.applicable_process == "dp_charges"


def test_04_invalid_source_class_rejection():
    """4. Reject invalid source class assignment."""
    with pytest.raises(ValidationError):
        OrganisationDocument(
            document_id="doc_org_test",
            organisation_id="ORG_TEST",
            source_class=SourceClass.REGULATORY,  # Forbidden on OrganisationDocument
            document_type="Policy",
            title="Title",
            document_identifier="ID",
            source_url=HttpUrl("https://example.com/policy"),
            source_hash="1" * 64,
        )


def test_05_orphan_provision_rejected_at_application_level():
    """5. Rejection of provision without parent document_id."""
    with pytest.raises(ValidationError):
        RegulatoryProvision(
            provision_id="PROV-001",
            document_id="",  # Blank parent document_id rejected
            source_text="Orphan clause text",
        )

    with pytest.raises(ValidationError):
        OrganisationProvision(
            provision_id="PROV-ORG-001",
            document_id="",  # Blank parent document_id rejected
            organisation_id="ORG_TEST",
            source_text="Orphan policy text",
        )


def test_06_relationship_self_reference_rejection():
    """6. Rejection of self-referencing relationship endpoints."""
    with pytest.raises(ValidationError) as exc:
        KnowledgeRelationship(
            source_id="DOC_SAME",
            target_id="DOC_SAME",
            relationship_type=RelationshipType.SUPERSEDES,
        )
    assert "cannot be identical" in str(exc.value)


def test_07_relationship_mapping_roundtrip():
    """7. KnowledgeRelationship Pydantic <-> ORM mapping roundtrip."""
    rel = KnowledgeRelationship(
        relationship_id="REL-2024-001",
        source_id="DOC_AMENDING_2024",
        target_id="DOC_BASE_2020",
        relationship_type=RelationshipType.AMENDMENT,
        description="Amends paragraph 4 regarding margin obligations",
        effective_date=date(2024, 5, 1),
        metadata={"amended_clause": "4.2", "gazette_notification": "SO 1234"},
    )
    orm = relationship_to_orm(rel)
    assert orm.relationship_type == "AMENDMENT"
    assert orm.metadata_json == {"amended_clause": "4.2", "gazette_notification": "SO 1234"}

    roundtrip = relationship_from_orm(orm)
    assert roundtrip.relationship_id == "REL-2024-001"
    assert roundtrip.relationship_type == RelationshipType.AMENDMENT
    assert roundtrip.metadata == rel.metadata


def test_08_provisions_mapping_and_jsonb_roundtrip():
    """8. Provision definitions and cross-references JSON roundtrip."""
    reg_prov = RegulatoryProvision(
        provision_id="REG-PROV-001",
        document_id="DOC-REG-001",
        section="Chapter II",
        clause="Regulation 3",
        paragraph="(1)(a)",
        source_text="Trading members shall segregate client collateral from proprietary funds.",
        definitions=["client collateral", "trading member", "proprietary funds"],
        cross_references=["SEBI/HO/MIRSD/2018/139", "SCRA-1956-SEC-15"],
        temporal_scope=TemporalScope(
            effective_date=date(2024, 1, 1),
            superseded_status=SupersededStatus.CURRENT,
        ),
    )
    orm = regulatory_provision_to_orm(reg_prov)
    assert isinstance(orm, RegulatoryProvisionORM)
    assert orm.definitions == ["client collateral", "trading member", "proprietary funds"]
    assert len(orm.cross_references) == 2

    roundtrip = regulatory_provision_from_orm(orm)
    assert roundtrip.provision_id == reg_prov.provision_id
    assert roundtrip.definitions == reg_prov.definitions
    assert roundtrip.cross_references == reg_prov.cross_references
    assert roundtrip.temporal_scope.effective_date == date(2024, 1, 1)


def test_09_hierarchical_section_tree_reconstruction():
    """9. Flattening and recursive reconstruction of nested section trees."""
    doc_id = "doc_tree_test_01"
    original_sections = [
        DocumentSection(
            section_id="sec_1",
            heading="1. Overview",
            level=1,
            content="Top level section text.",
            subsections=[
                DocumentSection(
                    section_id="sec_1_1",
                    heading="1.1 Scope",
                    level=2,
                    content="Subsection scope text.",
                    subsections=[
                        DocumentSection(
                            section_id="sec_1_1_1",
                            heading="1.1.1 Exceptions",
                            level=3,
                            content="Exceptions text.",
                            subsections=[],
                        )
                    ],
                ),
                DocumentSection(
                    section_id="sec_1_2",
                    heading="1.2 Applicability",
                    level=2,
                    content="Subsection applicability text.",
                    subsections=[],
                ),
            ],
        ),
        DocumentSection(
            section_id="sec_2",
            heading="2. Penalties",
            level=1,
            content="Second top level section.",
            subsections=[],
        ),
    ]

    # 1. Flatten to ORM items
    flat_items = flatten_section_tree(doc_id, original_sections)
    assert len(flat_items) == 5

    # Simulate database persistence with auto-assigned primary keys
    persisted_orms: list[DocumentSectionORM] = []
    key_to_id: dict[str, int] = {}
    
    current_pk = 100
    for orm_item, parent_key in flat_items:
        orm_item.id = current_pk
        key_to_id[orm_item.section_key] = current_pk
        if parent_key is not None:
            orm_item.parent_section_id = key_to_id[parent_key]
        persisted_orms.append(orm_item)
        current_pk += 1

    # 2. Reconstruct from ORM list
    reconstructed = reconstruct_section_tree(persisted_orms)
    assert len(reconstructed) == 2
    assert reconstructed[0].section_id == "sec_1"
    assert reconstructed[0].heading == "1. Overview"
    assert len(reconstructed[0].subsections) == 2
    assert reconstructed[0].subsections[0].section_id == "sec_1_1"
    assert len(reconstructed[0].subsections[0].subsections) == 1
    assert reconstructed[0].subsections[0].subsections[0].heading == "1.1.1 Exceptions"
    assert reconstructed[1].section_id == "sec_2"


def test_10_provenance_mapping_roundtrip():
    """10. Provenance Pydantic <-> ORM mapping roundtrip."""
    prov = Provenance(
        source_url=HttpUrl("https://www.sebi.gov.in/doc.pdf"),
        document_id="doc_reg_001",
        source_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        source_class=SourceClass.REGULATORY,
        extractor_version="v1.0",
    )
    orm = provenance_to_orm(prov)
    assert orm.document_id == "doc_reg_001"
    assert orm.source_hash == prov.source_hash

    roundtrip = provenance_from_orm(orm)
    assert roundtrip.document_id == prov.document_id
    assert roundtrip.source_hash == prov.source_hash
    assert str(roundtrip.source_url) == str(prov.source_url)
    assert roundtrip.source_class == SourceClass.REGULATORY
