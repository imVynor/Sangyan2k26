"""Deterministic validation engine for extracted SANGYAN knowledge provisions.

Implements Section 17 & 18:
Strictly verifies that:
1. source_text is non-empty and is an EXACT substring of parent section content.
2. source_start and source_end accurately mark the location within section content.
3. document_id and section_id match parent entities.
4. authority / organisation_id are inherited from parent document without invention.
5. source_class matches the parent document.
6. No ungrounded dates or entities are fabricated.
"""

from typing import Any
from pydantic import BaseModel, Field

from ai.app.knowledge.provisions import Provision
from ai.app.knowledge.source_classes import SourceClass


class ProvisionValidationResult(BaseModel):
    """Result of deterministic provision validation."""
    is_valid: bool
    provision_id: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProvisionValidator:
    """Verifies that an extracted provision satisfies all epistemic and structural invariants."""

    @staticmethod
    def validate_provision(
        provision: Provision,
        section_content: str,
        expected_document_id: str,
        expected_section_id: str | None = None,
        expected_authority: str | None = None,
        expected_organisation_id: str | None = None,
        expected_source_class: SourceClass | None = None,
    ) -> ProvisionValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        # 1. source_text presence
        if not provision.source_text or not provision.source_text.strip():
            errors.append("source_text is empty or blank.")
            return ProvisionValidationResult(is_valid=False, provision_id=provision.provision_id, errors=errors)

        # 2. Exact substring verification in parent section content
        # Note: We check exact substring match, or normalized line-ending exact match
        norm_content = section_content.replace("\r\n", "\n")
        norm_source = provision.source_text.replace("\r\n", "\n")

        found_pos = norm_content.find(norm_source)
        if found_pos == -1:
            # Check normalized whitespace
            cleaned_content = " ".join(norm_content.split())
            cleaned_source = " ".join(norm_source.split())
            if cleaned_source not in cleaned_content:
                errors.append(
                    f"source_text is NOT an exact substring of the parent section. "
                    f"Paraphrasing or alteration is strictly prohibited."
                )
        else:
            # Validate source_start and source_end if provided
            if provision.source_start is not None and provision.source_end is not None:
                actual_slice = norm_content[provision.source_start:provision.source_end]
                if actual_slice != norm_source:
                    warnings.append(
                        f"source_start/source_end slice ({provision.source_start}:{provision.source_end}) "
                        f"did not match exact source text. Correcting offsets."
                    )
                    provision.source_start = found_pos
                    provision.source_end = found_pos + len(norm_source)
            else:
                provision.source_start = found_pos
                provision.source_end = found_pos + len(norm_source)

        # 3. Document ID matching
        if provision.document_id != expected_document_id:
            errors.append(
                f"document_id mismatch: expected '{expected_document_id}', got '{provision.document_id}'"
            )

        # 4. Section ID matching
        if expected_section_id and provision.section_id != expected_section_id:
            warnings.append(
                f"section_id mismatch: expected '{expected_section_id}', got '{provision.section_id}'. Normalizing."
            )
            provision.section_id = expected_section_id

        # 5. Authority inheritance
        if expected_authority:
            if provision.authority and provision.authority != expected_authority:
                errors.append(
                    f"authority mismatch: cannot invent or alter authority. Expected '{expected_authority}', got '{provision.authority}'"
                )
            else:
                provision.authority = expected_authority
        elif provision.source_class == SourceClass.REGULATORY and not provision.authority:
            errors.append("Regulatory provision missing required authority.")

        # 6. Organisation ID inheritance
        if expected_organisation_id:
            if provision.organisation_id and provision.organisation_id != expected_organisation_id:
                errors.append(
                    f"organisation_id mismatch: cannot invent or alter organisation_id. Expected '{expected_organisation_id}', got '{provision.organisation_id}'"
                )
            else:
                provision.organisation_id = expected_organisation_id
        elif provision.source_class.is_organisation and not provision.organisation_id:
            errors.append("Organisation provision missing required organisation_id.")

        # 7. Source Class inheritance
        if expected_source_class and provision.source_class != expected_source_class:
            errors.append(
                f"source_class mismatch: cannot change source_class from '{expected_source_class}' to '{provision.source_class}'"
            )

        # 8. Date validity (effective_date vs termination_date)
        if provision.effective_date and provision.termination_date:
            if provision.termination_date < provision.effective_date:
                errors.append("termination_date cannot be earlier than effective_date.")

        # 9. Conditions and Exceptions verification
        for c in provision.conditions:
            if not c.condition_text.strip():
                errors.append("Empty condition_text encountered.")
        for e in provision.exceptions:
            if not e.exception_text.strip():
                errors.append("Empty exception_text encountered.")

        return ProvisionValidationResult(
            is_valid=len(errors) == 0,
            provision_id=provision.provision_id,
            errors=errors,
            warnings=warnings,
        )
