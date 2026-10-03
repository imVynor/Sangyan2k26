"""Strongly typed document models for SANGYAN knowledge representation.

Epistemic foundation:
- REGULATORY documents and ORGANISATION documents remain strictly separated.
- Nullable temporal fields are preserved: dates and versions must NEVER be invented.
- Strict Pydantic v2 validation for document_id, URLs, hashes, and source classes.
"""

from datetime import date, datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from ai.app.knowledge.provisions import RegulatoryProvision
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import SupersededStatus


class RegulatoryDocument(BaseModel):
    """Canonical representation of an official regulatory document.
    
    Includes Acts, Regulations, Circulars, Master Circulars, and Gazette Notifications.
    """
    document_id: str = Field(
        min_length=1,
        description="Unique system identifier for the regulatory document."
    )
    authority: str = Field(
        min_length=1,
        description="Issuing regulatory body (e.g. 'SEBI', 'RBI', 'NSE', 'BSE', 'CDSL', 'NSDL')."
    )
    jurisdiction: str = Field(
        default="India",
        description="Jurisdiction or domain (e.g. 'India', 'SEBI Securities Market')."
    )
    document_type: str = Field(
        description="Type: e.g. Act, Regulation, Circular, Master Circular, Notification, Guidance."
    )
    title: str = Field(
        min_length=1,
        description="Official title of the regulatory instrument."
    )
    document_identifier: str = Field(
        description="Official circular or notification number (e.g. 'SEBI/HO/MIRSD/DOS3/CIR/P/2018/139')."
    )
    publication_date: date | None = Field(
        default=None,
        description="Official publication date. Null if unavailable in source. Never invent dates."
    )
    effective_date: date | None = Field(
        default=None,
        description="Effective operative date. Null if unavailable in source."
    )
    termination_date: date | None = Field(
        default=None,
        description="Date repealed or terminated. Null if currently operative."
    )
    superseded_status: SupersededStatus = Field(
        default=SupersededStatus.UNKNOWN,
        description="Status: CURRENT, SUPERSEDED, PARTIALLY_AMENDED, or UNKNOWN."
    )
    source_url: HttpUrl = Field(
        description="Official URL from which the document was acquired."
    )
    source_hash: str = Field(
        min_length=8,
        description="Cryptographic SHA-256 hash of original ingested file/HTML."
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of retrieval."
    )
    source_class: SourceClass = Field(
        default=SourceClass.REGULATORY,
        description="Must be SourceClass.REGULATORY."
    )

    @field_validator("document_id")
    @classmethod
    def validate_doc_id(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("document_id is required and cannot be empty.")
        return trimmed

    @field_validator("source_class")
    @classmethod
    def validate_source_class(cls, v: SourceClass) -> SourceClass:
        if v != SourceClass.REGULATORY:
            raise ValueError(f"RegulatoryDocument must have source_class REGULATORY, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_dates_order(self) -> "RegulatoryDocument":
        if self.effective_date and self.termination_date:
            if self.termination_date < self.effective_date:
                raise ValueError("termination_date cannot be earlier than effective_date.")
        return self


class OrganisationDocument(BaseModel):
    """Canonical representation of an organisation's internal or client-facing policies.
    
    Includes broker policies, DP fee schedules, terms & conditions, grievance procedures.
    """
    document_id: str = Field(
        min_length=1,
        description="Unique system identifier for the organisation document."
    )
    organisation_id: str = Field(
        min_length=1,
        description="Unique identifier of intermediary (e.g. 'ORG_ZERODHA', 'ORG_GROWW')."
    )
    source_class: SourceClass = Field(
        description="Must be an organisation class: ORGANISATION_POLICY, ORGANISATION_PROCEDURE, or ORGANISATION_FAQ."
    )
    document_type: str = Field(
        description="Type: Policy, Terms and Conditions, Fee Schedule, Operational SOP, FAQ."
    )
    title: str = Field(
        min_length=1,
        description="Title of policy or document."
    )
    document_identifier: str = Field(
        description="Internal reference number, version string, or tariff code."
    )
    publication_date: date | None = Field(
        default=None,
        description="Published date. Null if unavailable in source."
    )
    effective_date: date | None = Field(
        default=None,
        description="Effective date. Null if unavailable in source."
    )
    termination_date: date | None = Field(
        default=None,
        description="Termination date. Null if active."
    )
    source_url: HttpUrl = Field(
        description="Public URL of the organisation document."
    )
    source_hash: str = Field(
        min_length=8,
        description="Cryptographic hash of raw document content."
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of retrieval."
    )
    superseded_status: SupersededStatus = Field(
        default=SupersededStatus.UNKNOWN,
        description="Status: CURRENT, SUPERSEDED, PARTIALLY_AMENDED, or UNKNOWN."
    )
    organisation_name: str | None = Field(
        default=None,
        description="Official human-readable name of intermediary (e.g. 'Zerodha Broking Limited')."
    )
    applicable_process: str | None = Field(
        default=None,
        description="Specific process governed (e.g. 'account_settlement', 'dp_charges', 'demat_debit')."
    )
    topic: str | None = Field(
        default=None,
        description="Primary topic category."
    )

    @field_validator("document_id")
    @classmethod
    def validate_doc_id(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("document_id is required and cannot be empty.")
        return trimmed

    @field_validator("source_class")
    @classmethod
    def validate_org_source_class(cls, v: SourceClass) -> SourceClass:
        valid_org_classes = {
            SourceClass.ORGANISATION_POLICY,
            SourceClass.ORGANISATION_PROCEDURE,
            SourceClass.ORGANISATION_FAQ,
        }
        if v not in valid_org_classes:
            raise ValueError(
                f"OrganisationDocument source_class must be one of {valid_org_classes}, got '{v}'"
            )
        return v

    @model_validator(mode="after")
    def validate_dates_order(self) -> "OrganisationDocument":
        if self.effective_date and self.termination_date:
            if self.termination_date < self.effective_date:
                raise ValueError("termination_date cannot be earlier than effective_date.")
        return self


class DocumentSection(BaseModel):
    """Structured hierarchical section within a document.
    
    Preserves document structure rather than flattening to plain text.
    """
    section_id: str = Field(description="Hierarchical section key, e.g. 'sec_3_1'")
    heading: str | None = Field(default=None, description="Heading or title of the section")
    level: int = Field(default=1, description="Nesting depth level (1=H1, 2=H2, etc.)")
    content: str = Field(description="Content text within this section")
    subsections: list["DocumentSection"] = Field(default_factory=list)


class NormalizedDocument(BaseModel):
    """Normalized structured document model preserving sections and provisions."""
    document_id: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    content: str = Field(description="Complete raw or normalized document text")
    sections: list[DocumentSection] = Field(default_factory=list)
    provisions: list[RegulatoryProvision] = Field(default_factory=list)
    source_hash: str = Field(min_length=8)


class SecondaryDocument(BaseModel):
    """Canonical representation of an unofficial commentary, legal analysis, or news source.
    
    Ranked strictly below statutory regulatory and official organisation documents.
    """
    document_id: str = Field(min_length=1)
    source_class: SourceClass = Field(default=SourceClass.SECONDARY_SOURCE)
    title: str = Field(min_length=1)
    document_type: str = "Commentary"
    publication_date: date | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    superseded_status: SupersededStatus = SupersededStatus.UNKNOWN
    source_url: HttpUrl
    source_hash: str = Field(min_length=8)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
