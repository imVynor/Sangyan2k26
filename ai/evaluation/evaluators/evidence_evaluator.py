"""Evidence and Claim Resolution Evaluator for SANGYAN (Phase 7A).

Epistemic foundation:
- Evaluates preservation of competing empirical claims without premature dropping.
- Verifies contradiction detection when user assertions conflict with documents.
- Evaluates evidence policy application: objective document > user statement.
"""

import logging
from typing import Any, Sequence

from ai.evaluation.corpus.models import EvaluationCase, StageEvaluationResult
from ai.evaluation.corpus.taxonomy import ClaimRelationshipType

logger = logging.getLogger("sangyan.evaluation.evidence")


class EvidenceEvaluator:
    """Evaluates evidentiary claim resolution, contradiction detection, and precedence."""

    def evaluate(
        self,
        case: EvaluationCase,
        actual_claims: Sequence[Any],
        detected_contradictions: Sequence[str] | None = None,
        resolved_fields: dict[str, Any] | None = None,
    ) -> StageEvaluationResult:
        if not case.expected_claims:
            return StageEvaluationResult(
                stage_name="EVIDENCE_RESOLUTION",
                passed=True,
                score=1.0,
                details={"skipped": True, "reason": "No expected claims defined"},
            )

        discrepancies: list[str] = []
        expected_contradictions = [
            c for c in case.expected_claims
            if c.relationship_type == ClaimRelationshipType.CONTRADICTORY
        ]

        actual_contradiction_list = list(detected_contradictions or [])

        # 1. Contradiction detection evaluation
        if expected_contradictions and not actual_contradiction_list:
            discrepancies.append(
                f"Expected contradiction between claims was NOT detected (Expected: {len(expected_contradictions)})"
            )

        # 2. Operative value resolution evaluation
        resolved_matches = 0
        total_resolutions = 0
        if resolved_fields:
            for exp_c in case.expected_claims:
                if exp_c.expected_resolution is not None:
                    total_resolutions += 1
                    actual_res = resolved_fields.get(exp_c.field_name)
                    if str(actual_res).strip().lower() == str(exp_c.expected_resolution).strip().lower():
                        resolved_matches += 1
                    else:
                        discrepancies.append(
                            f"Claim resolution mismatch for '{exp_c.field_name}': "
                            f"expected operative value {exp_c.expected_resolution!r}, got {actual_res!r}"
                        )

        passed = len(discrepancies) == 0
        score = 1.0 if passed else max(0.0, 1.0 - (len(discrepancies) * 0.3))

        return StageEvaluationResult(
            stage_name="EVIDENCE_RESOLUTION",
            passed=passed,
            score=score,
            details={
                "expected_claims_count": len(case.expected_claims),
                "actual_claims_count": len(actual_claims),
                "expected_contradictions": len(expected_contradictions),
                "detected_contradictions": len(actual_contradiction_list),
                "contradiction_detected": bool(actual_contradiction_list) if expected_contradictions else True,
            },
            discrepancies=discrepancies,
            failure_class="CONTRADICTION_UNDETECTED" if (expected_contradictions and not actual_contradiction_list) else None,
        )
