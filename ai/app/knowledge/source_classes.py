"""Canonical source classes for SANGYAN knowledge domains.

Epistemic foundation:
- REGULATORY knowledge and ORGANISATION knowledge MUST NOT be merged into one undifferentiated source type.
- Precedence is an explicit categorical property for downstream rule/assessment engines,
  NOT an implicit floating-point ranking score.
"""

from enum import Enum


class SourceClass(str, Enum):
    """Explicit source classification.
    
    Downstream assessment logic must check this class to distinguish
    between statutory regulations and commercial organization policies.
    """
    REGULATORY = "REGULATORY"
    ORGANISATION_POLICY = "ORGANISATION_POLICY"
    ORGANISATION_PROCEDURE = "ORGANISATION_PROCEDURE"
    ORGANISATION_FAQ = "ORGANISATION_FAQ"
    SECONDARY_SOURCE = "SECONDARY_SOURCE"

    @property
    def is_regulatory(self) -> bool:
        """Return True if this source represents public statutory/regulatory authority."""
        return self == SourceClass.REGULATORY

    @property
    def is_organisation(self) -> bool:
        """Return True if this source represents a specific market intermediary's documentation."""
        return self in {
            SourceClass.ORGANISATION_POLICY,
            SourceClass.ORGANISATION_PROCEDURE,
            SourceClass.ORGANISATION_FAQ,
        }
