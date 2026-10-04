"""Canonical provision models for SANGYAN knowledge representation.

Epistemic foundation:
- A provision MUST retain document provenance.
- A provision without a document_id is invalid.
- FACT != REGULATORY PROVISION: Provisions represent normative legal rules,
  not empirical assertions from a user narrative.
- Source text is authoritative: exact verbatim text from the source must be preserved.
  LLMs and extractors must NEVER substitute a paraphrase for authoritative source text.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import SupersededStatus, TemporalScope


class ProvisionType(str, Enum):
    """Categorical classification of atomic knowledge provisions."""
    RULE = "RULE"
    OBLIGATION = "OBLIGATION"
    RIGHT = "RIGHT"
    CONDITION = "CONDITION"
    EXCEPTION = "EXCEPTION"
    PROCEDURE = "PROCEDURE"
    DEFINITION = "DEFINITION"
    PROHIBITION = "PROHIBITION"
    ENTITLEMENT = "ENTITLEMENT"
    DISCLOSURE = "DISCLOSURE"
    TIMELINE = "TIMELINE"
    FEE_OR_CHARGE = "FEE_OR_CHARGE"
    ESCALATION = "ESCALATION"
    CROSS_REFERENCE = "CROSS_REFERENCE"
    SCOPE = "SCOPE"
    GENERAL_INFORMATION = "GENERAL_INFORMATION"


class Condition(BaseModel):
    """Explicit precondition or trigger for provision applicability."""
    condition_text: str = Field(description="Exact condition as expressed in source text.")


class ExceptionClause(BaseModel):
    """Explicit statutory or procedural exemption to a rule or obligation."""
    exception_text: str = Field(description="Text describing the exception or carve-out.")
    referenced_provision: str | None = Field(
        default=None,
        description="Optional citation or provision ID where exception is defined.",
    )


class ProcedureStep(BaseModel):
    """Sequential operational step in a grievance or administrative workflow."""
    step_number: int = Field(description="1-based sequence order.")
    step_text: str = Field(description="Procedural instruction for this step.")
    escalation_path: str | None = Field(
        default=None,
        description="Next authority or channel if step is unresolved (e.g. SCORES, ODR).",
    )


class Timeline(BaseModel):
    """Explicit statutory or contractual deadline or time window."""
    duration: int | float | None = Field(default=None, description="Numeric duration value (e.g. 30).")
    unit: str | None = Field(default=None, description="Time unit (e.g. 'DAYS', 'HOURS', 'MONTHS').")
    qualifier: str | None = Field(
        default=None,
        description="Exact statutory qualifier ('WITHIN', 'AFTER', 'BEFORE', 'WORKING_DAYS').",
    )
    timeline_text: str | None = Field(default=None, description="Raw textual representation.")


class FeeOrCharge(BaseModel):
    """Structured financial charge, fee, tariff, or brokerage rate."""
    amount: float | None = Field(default=None, description="Numeric fee amount if fixed.")
    currency: str = Field(default="INR", description="Currency code (e.g. 'INR').")
    unit: str | None = Field(default=None, description="Tariff unit (e.g. 'per transaction', 'per year', 'percentage').")
    transaction_type: str | None = Field(default=None, description="Applicable transaction (e.g. 'Equity Delivery', 'Pledge Creation').")
    applicability: str | None = Field(default=None, description="Scope or segment (e.g. 'Retail', 'BSDA').")
    conditions: list[str] = Field(default_factory=list, description="Explicit conditions attached to fee.")
    exemptions: list[str] = Field(default_factory=list, description="Explicit fee exemptions.")
    charge_text: str | None = Field(default=None, description="Raw textual rate representation.")


class Definition(BaseModel):
    """Statutory or contractual definition of a specialized term."""
    defined_term: str = Field(description="The word or phrase defined (e.g. 'Depository Participant').")
    definition_text: str = Field(description="Exact definition given in the source.")
    scope: str | None = Field(default=None, description="Document or section scope of this definition.")


class CrossReference(BaseModel):
    """Structured reference to another regulation, act, circular, or section."""
    target_reference: str = Field(description="Cited instrument (e.g. 'Regulation 30(4)', 'SCORES circular').")
    relationship_type: str = Field(default="REFERENCES", description="REFERENCES, SUBJECT_TO, IN_ACCORDANCE_WITH.")
    resolved_status: str = Field(
        default="CROSS_REFERENCE_UNRESOLVED",
        description="CROSS_REFERENCE_RESOLVED or CROSS_REFERENCE_UNRESOLVED.",
    )


class Provision(BaseModel):
    """Atomic, provenance-preserving representation of authoritative knowledge.
    
    Transforms raw structural DocumentSections into structured knowledge units
    participating in legal and procedural reasoning.
    """
    provision_id: str = Field(
        min_length=1,
        description="Unique deterministic identifier (e.g. 'prov_sebi_cir_001_p1_abc123').",
    )
    document_id: str = Field(
        min_length=1,
        description="Parent document identifier. Must match an authoritative document.",
    )
    section_id: str | None = Field(
        default=None,
        description="Key or ID of the structural section from which this provision was extracted.",
    )
    parent_provision_id: str | None = Field(
        default=None,
        description="Parent provision ID for hierarchical sub-rules or nested exceptions.",
    )
    provision_type: ProvisionType = Field(
        description="Primary classification (RULE, OBLIGATION, RIGHT, PROCEDURE, DEFINITION, etc.).",
    )
    source_text: str = Field(
        min_length=1,
        description="Exact verbatim substring copied from official source section.",
    )
    source_start: int | None = Field(
        default=None,
        description="Character start offset within parent section content.",
    )
    source_end: int | None = Field(
        default=None,
        description="Character end offset within parent section content.",
    )
    title: str | None = Field(
        default=None,
        description="Descriptive title or heading of the provision.",
    )
    section_reference: str | None = Field(
        default=None,
        description="Section numbering from document (e.g. 'Clause 3', 'Section 15').",
    )
    clause_reference: str | None = Field(
        default=None,
        description="Sub-clause reference (e.g. '(a)(i)').",
    )
    authority: str | None = Field(
        default=None,
        description="Issuing regulatory body (SEBI, NSE, BSE, CDSL, NSDL). Inherited from document.",
    )
    organisation_id: str | None = Field(
        default=None,
        description="Intermediary ID (ORG_ZERODHA, etc.). Inherited from document.",
    )
    source_class: SourceClass = Field(
        description="REGULATORY, ORGANISATION_POLICY, ORGANISATION_PROCEDURE, ORGANISATION_FAQ.",
    )
    topic: list[str] = Field(
        default_factory=list,
        description="Domain topics (e.g. 'investor_grievance', 'dp_charges', 'brokerage').",
    )
    process: str | None = Field(
        default=None,
        description="Specific financial/legal workflow (e.g. 'grievance', 'pledge', 'account_closure').",
    )
    applicable_entity: list[str] = Field(
        default_factory=list,
        description="Target entities (e.g. ['investor', 'stock_broker', 'depository_participant']).",
    )
    effective_date: date | None = Field(
        default=None,
        description="Effective date of this provision.",
    )
    termination_date: date | None = Field(
        default=None,
        description="Termination or repeal date if applicable.",
    )
    temporal_status: SupersededStatus = Field(
        default=SupersededStatus.UNKNOWN,
        description="CURRENT, SUPERSEDED, PARTIALLY_AMENDED, or UNKNOWN.",
    )
    provenance: Provenance | None = Field(
        default=None,
        description="Provenance record linking back to canonical origin URL and content hash.",
    )
    conditions: list[Condition] = Field(
        default_factory=list,
        description="Explicit preconditions for rule applicability.",
    )
    exceptions: list[ExceptionClause] = Field(
        default_factory=list,
        description="Explicit exceptions or exemptions.",
    )
    procedures: list[ProcedureStep] = Field(
        default_factory=list,
        description="Ordered procedural steps.",
    )
    timelines: list[Timeline] = Field(
        default_factory=list,
        description="Explicit statutory or operational deadlines.",
    )
    fees: list[FeeOrCharge] = Field(
        default_factory=list,
        description="Explicit fees, brokerage rates, or DP charges.",
    )
    definitions: list[Definition] = Field(
        default_factory=list,
        description="Defined terms and definitions.",
    )
    cross_references: list[CrossReference] = Field(
        default_factory=list,
        description="Explicit citations to external regulations or circulars.",
    )
    extraction_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extractor version, extraction method, confidence, and timestamps.",
    )

    @field_validator("provision_id")
    @classmethod
    def validate_provision_id(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("provision_id cannot be blank.")
        return trimmed

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("document_id cannot be blank.")
        return trimmed

    @field_validator("source_text")
    @classmethod
    def validate_source_text(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("source_text cannot be blank.")
        return trimmed

    @model_validator(mode="after")
    def validate_invariants(self) -> "Provision":
        if self.source_class.is_organisation:
            if not self.organisation_id or not self.organisation_id.strip():
                raise ValueError("organisation_id is required when source_class is an organisation type.")
        if self.source_class == SourceClass.REGULATORY:
            if not self.authority or not self.authority.strip():
                raise ValueError("authority is required when source_class is REGULATORY.")
        return self


# Backward-compatible Phase 1A models
class RegulatoryProvision(BaseModel):
    """Canonical representation of an operative regulatory clause, section, or rule.
    
    Must always remain tethered to its parent document_id.
    """
    provision_id: str = Field(
        min_length=1,
        description="Unique identifier for this provision (e.g. 'SEBI-LODR-REG-30(4)')."
    )
    document_id: str = Field(
        min_length=1,
        description="Parent document identifier. A provision without document_id is strictly invalid."
    )
    section: str | None = Field(
        default=None,
        description="Section number or heading (e.g. 'Section 11(2)')."
    )
    clause: str | None = Field(
        default=None,
        description="Specific clause identifier (e.g. 'Clause 4(a)')."
    )
    paragraph: str | None = Field(
        default=None,
        description="Paragraph or sub-paragraph designation."
    )
    source_text: str = Field(
        min_length=1,
        description="Exact verbatim text of the provision as published."
    )
    definitions: list[str] = Field(
        default_factory=list,
        description="Legal definitions established or relied upon in this provision."
    )
    cross_references: list[str] = Field(
        default_factory=list,
        description="Identifiers or citations to external regulations, circulars, or acts referenced."
    )
    temporal_scope: TemporalScope = Field(
        default_factory=TemporalScope,
        description="Temporal validity window of this specific provision."
    )
    provenance: Provenance | None = Field(
        default=None,
        description="Detailed provenance record linking directly to source publication."
    )

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("Provision MUST have a valid non-empty document_id.")
        return trimmed

    @field_validator("provision_id")
    @classmethod
    def validate_provision_id(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("provision_id cannot be blank.")
        return trimmed

    @field_validator("source_text")
    @classmethod
    def validate_source_text(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("source_text cannot be empty.")
        return trimmed


class OrganisationProvision(BaseModel):
    """Specific operational rule, policy requirement, or fee condition of an intermediary."""
    provision_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    organisation_id: str = Field(min_length=1)
    section: str | None = None
    clause: str | None = None
    source_text: str = Field(min_length=1)
    applicable_process: str | None = None
    temporal_scope: TemporalScope = Field(default_factory=TemporalScope)
    provenance: Provenance | None = None

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("OrganisationProvision MUST have a non-empty document_id.")
        return trimmed
