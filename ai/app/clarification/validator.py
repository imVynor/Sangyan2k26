"""Clarification Question Validator for SANGYAN Multi-Turn Dialogue.

Epistemic foundation:
- Ensures questions strictly correspond to genuine evidentiary gaps.
- Rejects hallucinated, irrelevant, or sensitive questions (INVALID_CLARIFICATION).
- Prohibits asking for passwords, OTPs, or already confirmed facts.
- Prohibits asking for fields the citizen explicitly declined.
"""

import logging
import re
from typing import Sequence

from ai.app.assessment.contracts import AssessmentResult
from ai.app.case.contracts import CaseState
from ai.app.clarification.contracts import ClarificationQuestion

logger = logging.getLogger("sangyan.clarification.validator")

# Sensitive/Prohibited concepts that should never be asked
PROHIBITED_TERMS = {
    "password", "pin", "otp", "one-time password", "cvv", "aadhar otp",
    "secret", "mother's maiden name", "login credentials"
}


class QuestionValidationError(Exception):
    """Raised when a generated clarification question violates epistemic or safety rules."""
    pass


class QuestionValidator:
    """Validates that clarification questions strictly align with genuine evidentiary requirements."""

    @classmethod
    def validate_question(
        cls,
        question: ClarificationQuestion,
        case_state: CaseState,
        assessment_result: AssessmentResult,
    ) -> tuple[bool, list[str]]:
        """Validate question against case state and missing requirements.
        
        Returns:
            (is_valid, validation_errors)
        """
        errors: list[str] = []
        q_text_lower = question.question.lower()

        # 1. Check for sensitive/prohibited terms
        for term in PROHIBITED_TERMS:
            if term in q_text_lower:
                errors.append(f"INVALID_CLARIFICATION: Question contains prohibited sensitive term '{term}'.")

        # 2. Check if field is already confirmed in case facts
        if question.field in case_state.facts and case_state.facts[question.field] is not None:
            # Check if it was contradicted in evidence
            is_contradicted = False
            for req in assessment_result.evidence_requirements:
                if req.field_name == question.field and req.status == "CONTRADICTED":
                    is_contradicted = True
                    break
            if not is_contradicted:
                errors.append(
                    f"INVALID_CLARIFICATION: Field '{question.field}' is already established as '{case_state.facts[question.field]}'."
                )

        # 3. Check if field was previously declined by citizen
        if question.field in case_state.declined_fields:
            errors.append(
                f"INVALID_CLARIFICATION: Field '{question.field}' was explicitly declined by user."
            )

        # 4. Check if field is actually an identified evidentiary requirement
        allowed_fields = set(assessment_result.missing_information)
        for req in assessment_result.evidence_requirements:
            allowed_fields.add(req.field_name)

        # Also allow general fields if temporality or coverage is unresolved
        if assessment_result.status == "TEMPORALITY_UNRESOLVED":
            allowed_fields.add("transaction_date")
        if assessment_result.status == "REGULATORY_COVERAGE_UNRESOLVED":
            allowed_fields.add("organisation")

        if question.field not in allowed_fields:
            errors.append(
                f"INVALID_CLARIFICATION: Field '{question.field}' is not an active missing requirement."
            )

        # 5. Semantic field reference check
        field_tokens = question.field.replace("_", " ").split()
        # Ensure at least one token from the field name appears in the question or reason
        has_field_match = any(token in q_text_lower for token in field_tokens)
        if not has_field_match:
            # Check multilingual or acceptable synonyms
            synonyms = {
                "transaction_type": ["delivery", "intraday", "type", "trade", "बिक्री", "ट्रेड"],
                "charged_amount": ["amount", "fee", "charge", "inr", "रुपये", "काटी"],
                "transaction_date": ["date", "day", "when", "तारीख", "दिन"],
                "organisation": ["broker", "participant", "depository", "ब्रोकर"],
                "is_bsda": ["bsda", "demat", "basic"],
            }
            allowed_synonyms = synonyms.get(question.field, [])
            if not any(s in q_text_lower for s in allowed_synonyms):
                errors.append(
                    f"INVALID_CLARIFICATION: Question text '{question.question}' does not reference target field '{question.field}'."
                )

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning("Question validation failed: %s", errors)
        return is_valid, errors
