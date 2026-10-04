"""Unit tests for Phase 1A foundational knowledge models and contracts.

Strictly covers minimum 20 required test scenarios:
1. Valid regulatory document
2. Missing required document_id
3. Invalid source URL
4. Valid organisation document
5. Invalid source class
6. Valid provision
7. Provision without document_id
8. Valid amendment relationship
9. Invalid relationship endpoint
10. Temporal document with effective date
11. Temporal document with termination date
12. CURRENT status
13. SUPERSEDED status
14. PARTIALLY_AMENDED status
15. UNKNOWN status
16. Valid retrieval chunk
17. Chunk preserving provenance
18. Organisation-specific chunk
19. Regulatory chunk
20. Case knowledge cannot be substituted for regulatory knowledge
"""

from datetime import date, datetime, timezone
import pytest
from pydantic import ValidationError

from ai.app.knowledge.documents import (
    DocumentSection,
    NormalizedDocument,
    OrganisationDocument,
    RegulatoryDocument,
)
from ai.app.knowledge.models import RetrievalChunk
from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.provisions import RegulatoryProvision
from ai.app.knowledge.relationships import KnowledgeRelationship, RelationshipType
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import (
    SupersededStatus,
    TemporalResolutionState,
    TemporalScope,
)
from ai.app.models.schemas import Fact, Claim, CaseUnderstanding, EpistemicStatus
from ai.app.validation.knowledge import (
    CaseKnowledgeBoundaryError,
    assert_not_case_state,
    CitationResolutionRequest,
    VersionResolutionRequest,
)


# =====================================================================
# Synthetic Fixture Helpers
# =====================================================================

def make_synthetic_regulatory_doc(**overrides) -> dict:
    """Return dictionary for a synthetic regulatory document fixture."""
    base = {
        "document_id": "REG-SYNTH-2024-001",
        "authority": "SEBI",
        "jurisdiction": "India",
        "document_type": "Circular",
        "title": "Example Regulatory Circular on Account Maintenance",
        "document_identifier": "SEBI/EXAMPLE/SYNTH/2024/01",
        "publication_date": date(2024, 1, 15),
        "effective_date": date(2024, 2, 1),
        "termination_date": None,
        "superseded_status": SupersededStatus.CURRENT,
        "source_url": "https://www.example.gov.in/sebi/circular_2024_01.pdf",
        "source_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "retrieved_at": datetime.now(timezone.utc),
        "source_class": SourceClass.REGULATORY,
    }
    base.update(overrides)
    return base


def make_synthetic_org_doc(**overrides) -> dict:
    """Return dictionary for a synthetic organisation document fixture."""
    base = {
        "document_id": "ORG-DOC-BROKER-001",
        "organisation_id": "ORG_EXAMPLE_BROKER",
        "organisation_name": "Example Discount Brokerage Ltd",
        "source_class": SourceClass.ORGANISATION_POLICY,
        "document_type": "Fee Schedule",
        "title": "Example Broker Fee Policy and Tariff Schedule",
        "document_identifier": "TARIFF-REV-2024-V1",
        "publication_date": date(2024, 1, 1),
        "effective_date": date(2024, 1, 1),
        "termination_date": None,
        "superseded_status": SupersededStatus.CURRENT,
        "source_url": "https://www.examplebroker.com/tariffs/fee_schedule_2024.html",
        "source_hash": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
        "retrieved_at": datetime.now(timezone.utc),
        "applicable_process": "dp_charges",
        "topic": "depository_charges",
    }
    base.update(overrides)
    return base


# =====================================================================
# Required Test Scenarios (1 to 20)
# =====================================================================

def test_01_valid_regulatory_document():
    """1. Valid regulatory document."""
    data = make_synthetic_regulatory_doc()
    doc = RegulatoryDocument.model_validate(data)
    assert doc.document_id == "REG-SYNTH-2024-001"
    assert doc.authority == "SEBI"
    assert doc.source_class == SourceClass.REGULATORY
    assert str(doc.source_url) == "https://www.example.gov.in/sebi/circular_2024_01.pdf"
    assert doc.effective_date == date(2024, 2, 1)


def test_02_missing_required_document_id():
    """2. Missing required document_id."""
    data = make_synthetic_regulatory_doc()
    del data["document_id"]
    with pytest.raises(ValidationError) as exc:
        RegulatoryDocument.model_validate(data)
    assert "document_id" in str(exc.value)

    # Empty string should also be rejected
    data["document_id"] = "   "
    with pytest.raises(ValidationError):
        RegulatoryDocument.model_validate(data)


def test_03_invalid_source_url():
    """3. Invalid source URL."""
    data = make_synthetic_regulatory_doc(source_url="not-a-valid-http-url")
    with pytest.raises(ValidationError) as exc:
        RegulatoryDocument.model_validate(data)
    assert "source_url" in str(exc.value)


def test_04_valid_organisation_document():
    """4. Valid organisation document."""
    data = make_synthetic_org_doc()
    doc = OrganisationDocument.model_validate(data)
    assert doc.document_id == "ORG-DOC-BROKER-001"
    assert doc.organisation_id == "ORG_EXAMPLE_BROKER"
    assert doc.source_class == SourceClass.ORGANISATION_POLICY
    assert doc.applicable_process == "dp_charges"


def test_05_invalid_source_class():
    """5. Invalid source class for organisation document."""
    # Attempting to set REGULATORY on an OrganisationDocument must fail
    data = make_synthetic_org_doc(source_class=SourceClass.REGULATORY)
    with pytest.raises(ValidationError) as exc:
        OrganisationDocument.model_validate(data)
    assert "source_class must be one of" in str(exc.value)

    # Unrecognized source class string must fail enum validation
    data = make_synthetic_org_doc(source_class="COMPLETELY_INVALID_CLASS")
    with pytest.raises(ValidationError):
        OrganisationDocument.model_validate(data)


def test_06_valid_provision():
    """6. Valid provision retaining document provenance."""
    prov = RegulatoryProvision(
        provision_id="REG-SYNTH-2024-001-CLAUSE-4",
        document_id="REG-SYNTH-2024-001",
        section="Section 4",
        clause="Clause 4(a)",
        source_text="Brokers shall not levy unauthorized account charges without prior disclosure.",
        definitions=["unauthorized account charges"],
        cross_references=["SEBI-ACT-1992-SEC-11"],
    )
    assert prov.provision_id == "REG-SYNTH-2024-001-CLAUSE-4"
    assert prov.document_id == "REG-SYNTH-2024-001"
    assert len(prov.definitions) == 1
    assert len(prov.cross_references) == 1


def test_07_provision_without_document_id():
    """7. Provision without document_id is invalid."""
    with pytest.raises(ValidationError):
        RegulatoryProvision(
            provision_id="ORPHAN-PROVISION-01",
            document_id="",  # Blank document_id forbidden
            source_text="Orphan clause text",
        )


def test_08_valid_amendment_relationship():
    """8. Valid amendment relationship."""
    rel = KnowledgeRelationship(
        relationship_id="REL-AMEND-001",
        source_id="REG-SYNTH-2024-002",
        target_id="REG-SYNTH-2018-MASTER",
        relationship_type=RelationshipType.AMENDMENT,
        description="Amends paragraph 3.2 of Master Circular",
        effective_date=date(2024, 6, 1),
    )
    assert rel.relationship_type == RelationshipType.AMENDMENT
    assert rel.source_id == "REG-SYNTH-2024-002"
    assert rel.target_id == "REG-SYNTH-2018-MASTER"


def test_09_invalid_relationship_endpoint():
    """9. Invalid relationship endpoint (self-referencing or empty)."""
    # Self-referencing impossible relationship
    with pytest.raises(ValidationError) as exc:
        KnowledgeRelationship(
            source_id="REG-SYNTH-2024-001",
            target_id="REG-SYNTH-2024-001",
            relationship_type=RelationshipType.SUPERSEDES,
        )
    assert "cannot be identical" in str(exc.value)

    # Empty endpoint
    with pytest.raises(ValidationError):
        KnowledgeRelationship(
            source_id="",
            target_id="REG-SYNTH-2024-001",
            relationship_type=RelationshipType.PART_OF,
        )


def test_10_temporal_document_with_effective_date():
    """10. Temporal document with effective date."""
    scope = TemporalScope(
        publication_date=date(2024, 1, 1),
        effective_date=date(2024, 3, 1),
        superseded_status=SupersededStatus.CURRENT,
    )
    # Incident before effective date -> NOT_YET_EFFECTIVE
    assert scope.check_applicability(date(2024, 2, 15)) == TemporalResolutionState.NOT_YET_EFFECTIVE
    # Incident on or after effective date -> APPLICABLE
    assert scope.check_applicability(date(2024, 3, 1)) == TemporalResolutionState.APPLICABLE
    assert scope.check_applicability(date(2024, 5, 10)) == TemporalResolutionState.APPLICABLE


def test_11_temporal_document_with_termination_date():
    """11. Temporal document with termination date."""
    scope = TemporalScope(
        effective_date=date(2020, 1, 1),
        termination_date=date(2023, 12, 31),
        superseded_status=SupersededStatus.SUPERSEDED,
    )
    # Incident during active period -> APPLICABLE
    assert scope.check_applicability(date(2022, 6, 1)) == TemporalResolutionState.APPLICABLE
    # Incident after termination date -> EXPIRED_OR_TERMINATED or SUPERSEDED
    assert scope.check_applicability(date(2024, 1, 1)) in {
        TemporalResolutionState.EXPIRED_OR_TERMINATED,
        TemporalResolutionState.SUPERSEDED,
    }

    # Termination date preceding effective date must raise validation error
    with pytest.raises(ValidationError) as exc:
        TemporalScope(
            effective_date=date(2024, 1, 1),
            termination_date=date(2023, 1, 1),
        )
    assert "cannot be earlier than effective_date" in str(exc.value)


def test_12_current_status():
    """12. CURRENT status representation."""
    doc = RegulatoryDocument.model_validate(
        make_synthetic_regulatory_doc(superseded_status=SupersededStatus.CURRENT)
    )
    assert doc.superseded_status == SupersededStatus.CURRENT
    assert doc.superseded_status.value == "CURRENT"


def test_13_superseded_status():
    """13. SUPERSEDED status representation."""
    doc = RegulatoryDocument.model_validate(
        make_synthetic_regulatory_doc(superseded_status=SupersededStatus.SUPERSEDED)
    )
    assert doc.superseded_status == SupersededStatus.SUPERSEDED
    assert doc.superseded_status.value == "SUPERSEDED"


def test_14_partially_amended_status():
    """14. PARTIALLY_AMENDED status representation."""
    doc = RegulatoryDocument.model_validate(
        make_synthetic_regulatory_doc(superseded_status=SupersededStatus.PARTIALLY_AMENDED)
    )
    assert doc.superseded_status == SupersededStatus.PARTIALLY_AMENDED
    assert doc.superseded_status.value == "PARTIALLY_AMENDED"


def test_15_unknown_status():
    """15. UNKNOWN status representation."""
    doc = RegulatoryDocument.model_validate(
        make_synthetic_regulatory_doc(superseded_status=SupersededStatus.UNKNOWN)
    )
    assert doc.superseded_status == SupersededStatus.UNKNOWN
    assert doc.superseded_status.value == "UNKNOWN"


def test_16_valid_retrieval_chunk():
    """16. Valid retrieval chunk."""
    chunk = RetrievalChunk(
        chunk_id="CHK-REG-001-01",
        document_id="REG-SYNTH-2024-001",
        provision_id="REG-SYNTH-2024-001-CLAUSE-4",
        text="Brokers shall not levy unauthorized account charges without prior disclosure.",
        section="Section 4 > Clause 4(a)",
        source_class=SourceClass.REGULATORY,
        authority="SEBI",
        effective_date=date(2024, 2, 1),
    )
    assert chunk.chunk_id == "CHK-REG-001-01"
    assert chunk.document_id == "REG-SYNTH-2024-001"
    assert chunk.provision_id == "REG-SYNTH-2024-001-CLAUSE-4"
    assert chunk.authority == "SEBI"


def test_17_chunk_preserving_provenance():
    """17. Chunk preserving provenance back to source document."""
    chunk = RetrievalChunk(
        chunk_id="CHK-ORG-001-02",
        document_id="ORG-DOC-BROKER-001",
        provision_id="ORG-PROV-DP-01",
        text="A depository participant fee of Rs 15.93 per ISIN debit shall apply.",
        section="Tariff Schedule > Demat Charges",
        source_class=SourceClass.ORGANISATION_POLICY,
        organisation_id="ORG_EXAMPLE_BROKER",
        effective_date=date(2024, 1, 1),
        termination_date=None,
    )
    assert chunk.document_id == "ORG-DOC-BROKER-001"
    assert chunk.provision_id == "ORG-PROV-DP-01"
    assert chunk.source_class == SourceClass.ORGANISATION_POLICY
    assert chunk.organisation_id == "ORG_EXAMPLE_BROKER"


def test_18_organisation_specific_chunk():
    """18. Organisation-specific chunk distinction."""
    chunk = RetrievalChunk(
        chunk_id="CHK-ORG-001-03",
        document_id="ORG-DOC-BROKER-001",
        text="Quarterly account maintenance charge is billed at the end of each calendar quarter.",
        source_class=SourceClass.ORGANISATION_POLICY,
        organisation_id="ORG_EXAMPLE_BROKER",
    )
    assert chunk.is_organisation is True
    assert chunk.is_regulatory is False
    assert chunk.organisation_id == "ORG_EXAMPLE_BROKER"


def test_19_regulatory_chunk():
    """19. Regulatory chunk distinction."""
    chunk = RetrievalChunk(
        chunk_id="CHK-REG-001-02",
        document_id="REG-SYNTH-2024-001",
        text="All depositories and depository participants shall comply with circular specifications.",
        source_class=SourceClass.REGULATORY,
        authority="SEBI",
    )
    assert chunk.is_regulatory is True
    assert chunk.is_organisation is False
    assert chunk.authority == "SEBI"


def test_20_case_knowledge_cannot_be_substituted_for_regulatory_knowledge():
    """20. Case knowledge cannot be substituted for regulatory knowledge."""
    case_fact = Fact(
        statement="User states ₹500 was deducted on 15th Sep",
        status=EpistemicStatus.USER_ASSERTED,
        source="user_narrative",
    )
    case_claim = Claim(
        statement="User alleges debit violates SEBI rules",
        status=EpistemicStatus.USER_ASSERTED,
    )
    case_understanding = CaseUnderstanding(
        intent="report_unauthorized_debit",
        facts=[case_fact],
        claims=[case_claim],
    )

    # Passing case state where knowledge is expected must be rejected
    with pytest.raises(CaseKnowledgeBoundaryError) as exc1:
        assert_not_case_state(case_fact)
    assert "Fact' belongs to Case State domain" in str(exc1.value)

    with pytest.raises(CaseKnowledgeBoundaryError) as exc2:
        assert_not_case_state(case_claim)
    assert "Claim' belongs to Case State domain" in str(exc2.value)

    with pytest.raises(CaseKnowledgeBoundaryError) as exc3:
        assert_not_case_state(case_understanding)
    assert "CaseUnderstanding' belongs to Case State domain" in str(exc3.value)


# =====================================================================
# Additional Contract & Normalization Tests
# =====================================================================

def test_normalized_document_structure():
    """Verify NormalizedDocument retains hierarchical sections and provisions."""
    doc = NormalizedDocument(
        document_id="NORM-DOC-001",
        metadata={"jurisdiction": "India", "authority": "SEBI"},
        content="Full raw text of the circular...",
        sections=[
            DocumentSection(
                section_id="sec_1",
                heading="1. Background",
                level=1,
                content="Background context...",
                subsections=[
                    DocumentSection(
                        section_id="sec_1_1",
                        heading="1.1 Scope",
                        level=2,
                        content="Applies to all registered stock brokers.",
                    )
                ],
            )
        ],
        provisions=[
            RegulatoryProvision(
                provision_id="PROV-001",
                document_id="NORM-DOC-001",
                source_text="Stock brokers must maintain settlement records.",
            )
        ],
        source_hash="b" * 64,
    )
    assert doc.document_id == "NORM-DOC-001"
    assert len(doc.sections) == 1
    assert len(doc.sections[0].subsections) == 1
    assert doc.sections[0].subsections[0].heading == "1.1 Scope"
    assert len(doc.provisions) == 1


def test_provenance_immutability_and_hash():
    """Verify Provenance model rejects short hashes or blank document IDs."""
    with pytest.raises(ValidationError):
        Provenance(
            source_url="https://www.example.gov.in/doc.pdf",
            document_id="",  # Blank forbidden
            source_hash="short",  # < 8 chars forbidden
            source_class=SourceClass.REGULATORY,
        )


def test_temporal_temporality_unresolved():
    """When both effective date and publication date are missing, status is TEMPORALITY_UNRESOLVED."""
    scope = TemporalScope(
        publication_date=None,
        effective_date=None,
        superseded_status=SupersededStatus.UNKNOWN,
    )
    assert scope.check_applicability(date(2024, 1, 1)) == TemporalResolutionState.TEMPORALITY_UNRESOLVED
