"""Temporal reasoning primitives and applicability states for SANGYAN knowledge.

Epistemic foundation:
- Do NOT assume that the newest document is the applicable document.
- SANGYAN must evaluate rules based on the incident date, not retrieval date.
- Do NOT invent dates: fields are strictly nullable if missing in source.
- If applicability cannot be established, represent TEMPORALITY_UNRESOLVED explicitly.
"""

from datetime import date
from enum import Enum
from pydantic import BaseModel, Field, model_validator


class SupersededStatus(str, Enum):
    """Status reflecting whether a document or provision has been replaced."""
    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    PARTIALLY_AMENDED = "PARTIALLY_AMENDED"
    UNKNOWN = "UNKNOWN"


class TemporalResolutionState(str, Enum):
    """Outcome state of temporal applicability evaluation."""
    APPLICABLE = "APPLICABLE"
    NOT_YET_EFFECTIVE = "NOT_YET_EFFECTIVE"
    EXPIRED_OR_TERMINATED = "EXPIRED_OR_TERMINATED"
    SUPERSEDED = "SUPERSEDED"
    TEMPORALITY_UNRESOLVED = "TEMPORALITY_UNRESOLVED"


class TemporalScope(BaseModel):
    """Temporal lifecycle bounds for documents, provisions, and rules."""
    publication_date: date | None = Field(
        default=None,
        description="Official gazette or release date. Null if unavailable in source."
    )
    effective_date: date | None = Field(
        default=None,
        description="Date from which the provisions acquire binding legal force."
    )
    termination_date: date | None = Field(
        default=None,
        description="Date on which the document or provision ceased to be effective."
    )
    superseded_status: SupersededStatus = Field(
        default=SupersededStatus.UNKNOWN,
        description="Whether this document has been superseded, amended, or is current."
    )

    @model_validator(mode="after")
    def validate_temporal_order(self) -> "TemporalScope":
        """Verify that termination date does not precede effective date."""
        if self.effective_date and self.termination_date:
            if self.termination_date < self.effective_date:
                raise ValueError(
                    f"termination_date ({self.termination_date}) cannot be earlier than "
                    f"effective_date ({self.effective_date})"
                )
        return self

    def check_applicability(self, target_date: date) -> TemporalResolutionState:
        """Evaluate temporal applicability against an incident date.
        
        Returns TEMPORALITY_UNRESOLVED if boundaries are unknown rather than guessing.
        """
        # If superseded entirely, it is not currently applicable unless investigating historical period
        if self.superseded_status == SupersededStatus.SUPERSEDED:
            if self.termination_date and target_date > self.termination_date:
                return TemporalResolutionState.SUPERSEDED

        # If effective date is unknown, we cannot guarantee applicability deterministically
        if self.effective_date is None and self.publication_date is None:
            return TemporalResolutionState.TEMPORALITY_UNRESOLVED

        baseline_date = self.effective_date or self.publication_date
        if baseline_date and target_date < baseline_date:
            return TemporalResolutionState.NOT_YET_EFFECTIVE

        if self.termination_date and target_date > self.termination_date:
            return TemporalResolutionState.EXPIRED_OR_TERMINATED

        if self.effective_date is not None:
            return TemporalResolutionState.APPLICABLE

        # If only publication date was known, effective date remains unresolved
        return TemporalResolutionState.TEMPORALITY_UNRESOLVED
