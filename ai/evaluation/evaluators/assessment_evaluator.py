"""Epistemic Assessment and Logical Chain Evaluator for SANGYAN (Phase 7A).

Epistemic foundation:
- Evaluates the deterministic assessment chain: facts -> conditions -> findings -> status.
- Strict safety invariants: zero false VIOLATION_CONFIRMED and zero false COMPLIANT_WITH_REGULATION.
- Evaluates exact numerical arithmetic correctness for compound financial disputes.
"""

from decimal import Decimal
import logging
from typing import Any

from ai.app.assessment.contracts import AssessmentResult, AssessmentStatus
from ai.evaluation.corpus.models import EvaluationCase, StageEvaluationResult

logger = logging.getLogger("sangyan.evaluation.assessment")


class AssessmentEvaluator:
    """Evaluates epistemic assessment determinations, conditions, and safety invariants."""

    def evaluate(
        self,
        case: EvaluationCase,
        actual_assessment: AssessmentResult | None,
        actual_financial: dict[str, Any] | None = None,
    ) -> tuple[StageEvaluationResult, bool, bool]:
        """Evaluate assessment result.

        Returns:
            (StageEvaluationResult, false_violation_flag, false_compliance_flag)
        """
        if not case.expected_assessment:
            return (
                StageEvaluationResult(
                    stage_name="ASSESSMENT",
                    passed=True,
                    score=1.0,
                    details={"skipped": True, "reason": "No expected_assessment defined"},
                ),
                False,
                False,
            )

        exp = case.expected_assessment
        discrepancies: list[str] = []
        false_violation = False
        false_compliance = False

        if actual_assessment is None:
            discrepancies.append("Assessment result is None (engine failed to evaluate)")
            return (
                StageEvaluationResult(
                    stage_name="ASSESSMENT",
                    passed=False,
                    score=0.0,
                    details={"actual_status": None, "expected_status": exp.expected_status.value},
                    discrepancies=discrepancies,
                    failure_class="ASSESSMENT_FAILED",
                ),
                False,
                False,
            )

        actual_status = actual_assessment.status
        acceptable_statuses = [exp.expected_status] + list(exp.acceptable_statuses)

        status_matched = actual_status in acceptable_statuses

        # 1. Safety invariant audit (Section 18)
        if actual_status == AssessmentStatus.VIOLATION_CONFIRMED and AssessmentStatus.VIOLATION_CONFIRMED not in acceptable_statuses:
            false_violation = True
            discrepancies.append(
                f"SAFETY INVARIANT VIOLATION: False VIOLATION_CONFIRMED! (Expected: {exp.expected_status.value})"
            )

        if actual_status == AssessmentStatus.COMPLIANT_WITH_REGULATION and AssessmentStatus.COMPLIANT_WITH_REGULATION not in acceptable_statuses:
            false_compliance = True
            discrepancies.append(
                f"SAFETY INVARIANT VIOLATION: False COMPLIANT_WITH_REGULATION! (Expected: {exp.expected_status.value})"
            )

        if not status_matched:
            discrepancies.append(
                f"Status mismatch: expected {exp.expected_status.value}, got {actual_status.value}"
            )

        # 2. Condition evaluation checks
        condition_score = 1.0
        if case.expected_conditions and actual_assessment.conditions:
            cond_matches = 0
            actual_cond_map = {c.condition_id: c.is_met for c in actual_assessment.conditions}
            for exp_c in case.expected_conditions:
                if exp_c.condition_id in actual_cond_map:
                    if actual_cond_map[exp_c.condition_id] == exp_c.expected_boolean:
                        cond_matches += 1
                    else:
                        discrepancies.append(
                            f"Condition mismatch '{exp_c.condition_id}': expected {exp_c.expected_boolean}, "
                            f"got {actual_cond_map[exp_c.condition_id]}"
                        )
                else:
                    discrepancies.append(f"Expected condition '{exp_c.condition_id}' not evaluated")

            condition_score = cond_matches / len(case.expected_conditions)

        # 3. Numerical arithmetic evaluation
        numerical_correct = True
        if case.expected_financial and actual_financial:
            exp_fin = case.expected_financial
            if exp_fin.total_expected is not None:
                actual_total = actual_financial.get("total_amount") or actual_financial.get("total_expected")
                if actual_total is not None:
                    try:
                        if Decimal(str(actual_total)) != exp_fin.total_expected:
                            numerical_correct = False
                            discrepancies.append(
                                f"Numerical mismatch in total: expected {exp_fin.total_expected}, got {actual_total}"
                            )
                    except Exception:
                        numerical_correct = False

        passed = status_matched and not false_violation and not false_compliance and numerical_correct
        score = (0.7 if status_matched else 0.0) + (0.3 * condition_score)
        if false_violation or false_compliance:
            score = 0.0

        return (
            StageEvaluationResult(
                stage_name="ASSESSMENT",
                passed=passed,
                score=score,
                details={
                    "expected_status": exp.expected_status.value,
                    "actual_status": actual_status.value,
                    "status_matched": status_matched,
                    "condition_score": condition_score,
                    "false_violation": false_violation,
                    "false_compliance": false_compliance,
                    "numerical_correct": numerical_correct,
                },
                discrepancies=discrepancies,
                failure_class="FALSE_VIOLATION" if false_violation else ("FALSE_COMPLIANCE" if false_compliance else ("STATUS_MISMATCH" if not status_matched else None)),
            ),
            false_violation,
            false_compliance,
        )
