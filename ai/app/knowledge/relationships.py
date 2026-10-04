"""Typed knowledge relationship models for SANGYAN.

Epistemic foundation:
Inter-document and inter-provision legal structures (amendments, exceptions,
supersessions) must be represented as typed entities rather than unstructured strings.
"""

from datetime import date
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator


class RelationshipType(str, Enum):
    """Canonical relationship classifications between knowledge entities."""
    AMENDMENT = "AMENDMENT"
    AMENDS = "AMENDS"
    SUPERSEDES = "SUPERSEDES"
    PARTIALLY_AMENDS = "PARTIALLY_AMENDS"
    REPLACES = "REPLACES"
    REFERENCES = "REFERENCES"
    CROSS_REFERENCE = "CROSS_REFERENCE"
    CLARIFIES = "CLARIFIES"
    EXTENDS = "EXTENDS"
    TERMINATES = "TERMINATES"
    DEFINITION_OF = "DEFINITION_OF"
    EXCEPTION_TO = "EXCEPTION_TO"
    PART_OF = "PART_OF"


class KnowledgeRelationship(BaseModel):
    """Directed, typed relationship between two knowledge entities (documents or provisions)."""
    relationship_id: str | None = Field(
        default=None,
        description="Optional unique identifier for this relationship record."
    )
    source_id: str = Field(
        min_length=1,
        description="Identifier of originating entity (e.g. amending circular or referencing clause)."
    )
    target_id: str = Field(
        min_length=1,
        description="Identifier of referenced entity (e.g. master circular being amended)."
    )
    relationship_type: RelationshipType = Field(
        description="Explicit semantic relationship type."
    )
    description: str | None = Field(
        default=None,
        description="Human-readable or legal context explaining the relationship."
    )
    effective_date: date | None = Field(
        default=None,
        description="Date when this legal relationship becomes operative."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured parameters (e.g. specific clause modified)."
    )

    @model_validator(mode="after")
    def validate_endpoints(self) -> "KnowledgeRelationship":
        """Reject invalid or impossible relationship endpoints."""
        src = self.source_id.strip() if self.source_id else ""
        tgt = self.target_id.strip() if self.target_id else ""

        if not src:
            raise ValueError("source_id cannot be empty.")
        if not tgt:
            raise ValueError("target_id cannot be empty.")
        if src == tgt:
            raise ValueError(
                f"Invalid self-referencing relationship: source_id '{src}' "
                f"cannot be identical to target_id '{tgt}'."
            )
        return self
