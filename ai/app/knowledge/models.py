"""Knowledge domain chunk models and core contracts.

Epistemic foundation:
- Retrieval chunks must retain full provenance to reconstruct the original source.
- Chunks do NOT include vector embeddings in Phase 1A.
- Case knowledge (Fact, Claim) and Regulatory Knowledge (Provision, Document) are
  mutually exclusive domains and must never be substituted for one another.
"""

from datetime import date
from pydantic import BaseModel, Field, field_validator

from ai.app.knowledge.source_classes import SourceClass


class RetrievalChunk(BaseModel):
    """Normalized retrieval unit linking granular text back to parent document and provision."""
    chunk_id: str = Field(
        min_length=1,
        description="Unique identifier for this retrieval unit (e.g. 'chk_sebi_lodr_30_1')."
    )
    document_id: str = Field(
        min_length=1,
        description="Parent document identifier."
    )
    provision_id: str | None = Field(
        default=None,
        description="Associated regulatory or organisation provision ID if aligned to a specific clause."
    )
    text: str = Field(
        min_length=1,
        description="Granular passage text for downstream indexing and retrieval."
    )
    section: str | None = Field(
        default=None,
        description="Section heading or structural path in the parent document."
    )
    source_class: SourceClass = Field(
        description="Categorical source class (REGULATORY, ORGANISATION_POLICY, etc.)."
    )
    organisation_id: str | None = Field(
        default=None,
        description="Intermediary ID if this chunk originated from an organisation document."
    )
    authority: str | None = Field(
        default=None,
        description="Regulatory body if this chunk originated from a regulatory document."
    )
    effective_date: date | None = Field(
        default=None,
        description="Effective date of the governing provision."
    )
    termination_date: date | None = Field(
        default=None,
        description="Termination date if repealed or superseded."
    )

    @field_validator("chunk_id", "document_id", "text")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("Required chunk fields cannot be empty or whitespace.")
        return trimmed

    @property
    def is_regulatory(self) -> bool:
        return self.source_class.is_regulatory

    @property
    def is_organisation(self) -> bool:
        return self.source_class.is_organisation
