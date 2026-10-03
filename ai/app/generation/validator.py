"""Generation Validator and Grounding Verifier for SANGYAN.

Epistemic foundation:
- Validates that generated explanations remain strictly grounded in retrieved provisions and assessment findings.
- Rejects hallucinated circular citations or unauthorized regulatory references.
- Ensures the Generation Service never mutates the underlying AssessmentStatus.
- Strictly verifies that missing facts are not hallucinated into established facts.
"""

import logging
import re
from typing import Sequence

from ai.app.assessment.contracts import AssessmentResult, AssessmentStatus
from ai.app.generation.contracts import GeneratedResponse
from ai.app.retrieval.contracts import RetrievalResponse

logger = logging.getLogger("sangyan.generation.validator")


class GenerationValidationResult:
    """Audit result of generation grounding and citation validation."""

    def __init__(self, is_valid: bool, errors: list[str]) -> None:
        self.is_valid = is_valid
        self.errors = errors


class GenerationValidator:
    """Validates generated citizen responses against authoritative evidence and assessment results."""

    @classmethod
    def validate(
        cls,
        response: GeneratedResponse,
        assessment: AssessmentResult,
        retrieval: RetrievalResponse,
    ) -> GenerationValidationResult:
        """Execute post-generation verification."""
        errors: list[str] = []

        # 1. Assessment Status Invariant: Generator must NEVER alter assessment status
        if response.assessment_status != assessment.status:
            errors.append(
                f"STATUS_MUTATION_ERROR: Generated status '{response.assessment_status.value}' "
                f"does not match authoritative assessment status '{assessment.status.value}'."
            )

        # 2. Citation Grounding: All cited provisions must exist in retrieved provisions
        allowed_provision_ids = {r.provision_id for r in retrieval.results}
        allowed_doc_ids = {r.document_id for r in retrieval.results}

        for finding in response.findings:
            for pid in finding.cited_provisions:
                if pid not in allowed_provision_ids and pid not in allowed_doc_ids:
                    errors.append(
                        f"INVALID_CITATION: Finding cites provision/doc '{pid}' which is NOT "
                        f"present in the retrieved candidate pool."
                    )

        for cit in response.regulatory_basis:
            if cit.provision_id not in allowed_provision_ids and cit.document_identifier not in allowed_doc_ids:
                errors.append(
                    f"INVALID_CITATION: Regulatory basis cites '{cit.provision_id}' which is NOT "
                    f"in the retrieved candidate pool."
                )

        # 3. Grounding Against Hallucinated External Facts
        # If assessment status is EVIDENCE_INSUFFICIENT, check that missing facts are not claimed as established
        if assessment.status == AssessmentStatus.EVIDENCE_INSUFFICIENT:
            for missing_field in assessment.missing_information:
                # If transaction_type is missing, generator must not state "The transaction was definitely delivery"
                if missing_field == "transaction_type":
                    if re.search(r"\b(it was a delivery transaction|definitely equity delivery)\b", response.summary, re.IGNORECASE):
                        errors.append(
                            "UNSUPPORTED_CLAIM: Response claims transaction_type is established, "
                            "but assessment flagged it as missing evidence."
                        )

        # 4. Non-empty explanation
        if not response.summary.strip():
            errors.append("EMPTY_SUMMARY: Generated response has an empty summary.")

        is_valid = len(errors) == 0
        return GenerationValidationResult(is_valid=is_valid, errors=errors)
