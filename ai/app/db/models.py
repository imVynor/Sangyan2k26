"""SQLAlchemy ORM models for SANGYAN knowledge persistence.

Persists:
1. regulatory_documents
2. organisation_documents
3. provenance
4. document_sections
5. regulatory_provisions
6. organisation_provisions
7. knowledge_relationships
8. ingestion_records
"""

from datetime import date, datetime
from typing import Any
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from ai.app.db.base import Base

# Dialect-agnostic JSONB representation
JSONType = JSON().with_variant(JSONB, "postgresql")
TSVectorType = TSVECTOR().with_variant(Text, "sqlite")
EmbeddingVectorType = Vector(768).with_variant(JSON(), "sqlite")



class RegulatoryDocumentORM(Base):
    """Relational table for official regulatory instruments."""
    __tablename__ = "regulatory_documents"

    document_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    authority: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(128), nullable=False, default="India")
    document_type: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    document_identifier: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    superseded_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_class: Mapped[str] = mapped_column(String(64), nullable=False, default="REGULATORY")

    # Relationships
    provisions: Mapped[list["RegulatoryProvisionORM"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sections: Mapped[list["DocumentSectionORM"]] = relationship(
        primaryjoin="foreign(DocumentSectionORM.document_id) == RegulatoryDocumentORM.document_id",
        cascade="all, delete-orphan",
        overlaps="sections",
        viewonly=True,
    )

    __table_args__ = (
        CheckConstraint("source_class = 'REGULATORY'", name="check_regulatory_source_class"),
        CheckConstraint(
            "termination_date IS NULL OR effective_date IS NULL OR termination_date >= effective_date",
            name="check_regulatory_dates_order",
        ),
        CheckConstraint(
            "superseded_status IN ('CURRENT', 'SUPERSEDED', 'PARTIALLY_AMENDED', 'UNKNOWN')",
            name="check_regulatory_superseded_status",
        ),
    )


class OrganisationDocumentORM(Base):
    """Relational table for intermediary policies, fee schedules, and procedures."""
    __tablename__ = "organisation_documents"

    document_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_class: Mapped[str] = mapped_column(String(64), nullable=False)
    document_type: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    document_identifier: Mapped[str] = mapped_column(String(256), nullable=False)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    superseded_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    organisation_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    applicable_process: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    topic: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Relationships
    provisions: Mapped[list["OrganisationProvisionORM"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sections: Mapped[list["DocumentSectionORM"]] = relationship(
        primaryjoin="foreign(DocumentSectionORM.document_id) == OrganisationDocumentORM.document_id",
        cascade="all, delete-orphan",
        overlaps="sections",
        viewonly=True,
    )

    __table_args__ = (
        CheckConstraint(
            "source_class IN ('ORGANISATION_POLICY', 'ORGANISATION_PROCEDURE', 'ORGANISATION_FAQ')",
            name="check_org_source_class",
        ),
        CheckConstraint(
            "termination_date IS NULL OR effective_date IS NULL OR termination_date >= effective_date",
            name="check_org_dates_order",
        ),
        CheckConstraint(
            "superseded_status IN ('CURRENT', 'SUPERSEDED', 'PARTIALLY_AMENDED', 'UNKNOWN')",
            name="check_org_superseded_status",
        ),
    )


class ProvenanceORM(Base):
    """Relational store for immutable provenance audit trails."""
    __tablename__ = "provenance"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_class: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("document_id", "source_hash", name="uq_provenance_doc_hash"),
    )


class DocumentSectionORM(Base):
    """Hierarchical section and structural block representation."""
    __tablename__ = "document_sections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_section_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("document_sections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Self-referencing tree hierarchy
    parent: Mapped["DocumentSectionORM | None"] = relationship(
        "DocumentSectionORM",
        remote_side=[id],
        back_populates="subsections",
    )
    subsections: Mapped[list["DocumentSectionORM"]] = relationship(
        "DocumentSectionORM",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="DocumentSectionORM.order_index",
    )

    __table_args__ = (
        UniqueConstraint("document_id", "section_key", name="uq_doc_sections_doc_key"),
        Index("ix_sections_doc_order", "document_id", "order_index"),
    )


class RegulatoryProvisionORM(Base):
    """Relational table for granular statutory/regulatory provisions."""
    __tablename__ = "regulatory_provisions"

    provision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("regulatory_documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section: Mapped[str | None] = mapped_column(String(256), nullable=True)
    clause: Mapped[str | None] = mapped_column(String(256), nullable=True)
    paragraph: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    definitions: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    cross_references: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    superseded_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")

    document: Mapped["RegulatoryDocumentORM"] = relationship(back_populates="provisions")


class OrganisationProvisionORM(Base):
    """Relational table for granular organisation policy terms and fee conditions."""
    __tablename__ = "organisation_provisions"

    provision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("organisation_documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organisation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    section: Mapped[str | None] = mapped_column(String(256), nullable=True)
    clause: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    applicable_process: Mapped[str | None] = mapped_column(String(128), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    superseded_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")

    document: Mapped["OrganisationDocumentORM"] = relationship(back_populates="provisions")


class KnowledgeRelationshipORM(Base):
    """Directed relational link between knowledge entities."""
    __tablename__ = "knowledge_relationships"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    relationship_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint("source_id != target_id", name="check_rel_source_target_distinct"),
        CheckConstraint(
            "relationship_type IN ('AMENDMENT', 'SUPERSEDES', 'CROSS_REFERENCE', 'DEFINITION_OF', 'EXCEPTION_TO', 'PART_OF')",
            name="check_rel_type_allowed",
        ),
    )


class IngestionRecordORM(Base):
    """Operational audit log of document ingestion attempts."""
    __tablename__ = "ingestion_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ingestion_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class KnowledgeProvisionORM(Base):
    """Relational table for atomic, normalized knowledge provisions."""
    __tablename__ = "knowledge_provisions"

    provision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    section_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    parent_provision_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    provision_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    clause_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    authority: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    organisation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_class: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    topic: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    process: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    applicable_entity: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    temporal_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN", index=True)
    conditions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    exceptions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    procedures_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    timelines_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    fees_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    definitions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    cross_references_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    extraction_metadata: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    search_vector: Mapped[Any | None] = mapped_column(TSVectorType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_knowledge_prov_doc_type", "document_id", "provision_type"),
        Index("ix_knowledge_prov_auth_proc", "authority", "process"),
        Index("ix_knowledge_prov_org_proc", "organisation_id", "process"),
    )


class KnowledgeProvisionEmbeddingORM(Base):
    """Relational table for provision dense embeddings."""
    __tablename__ = "knowledge_provision_embeddings"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("knowledge_provisions.provision_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding: Mapped[list[float]] = mapped_column(
        EmbeddingVectorType,
        nullable=False,
    )
    embedding_model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("provision_id", "embedding_model_id", "embedding_model_version", name="uq_prov_emb_model"),
        Index("ix_emb_model_version", "embedding_model_id", "embedding_model_version"),
    )
