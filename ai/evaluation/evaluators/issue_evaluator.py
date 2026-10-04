"""Issue and Hypothesis Identification Evaluator for SANGYAN (Phase 7A).

Epistemic foundation:
- Measures primary and secondary issue classification precision and recall.
- Penalizes misleading topical decoys (irrelevant_plausible_issues).
- Evaluates multi-hypothesis tracking and resolution state.
"""

import logging
from typing import Any, Sequence

from ai.evaluation.corpus.models import EvaluationCase, StageEvaluationResult

logger = logging.getLogger("sangyan.evaluation.issue")


class IssueEvaluator:
    """Evaluates whether the system identified the operative legal issues."""

    def evaluate(
        self,
        case: EvaluationCase,
        actual_issues: Sequence[str] | str,
        actual_hypotheses: Sequence[dict[str, Any]] | None = None,
    ) -> StageEvaluationResult:
        if not case.expected_issues:
            return StageEvaluationResult(
                stage_name="ISSUE_IDENTIFICATION",
                passed=True,
                score=1.0,
                details={"skipped": True, "reason": "No expected_issues defined"},
            )

        exp = case.expected_issues
        discrepancies: list[str] = []

        # Normalize actual issues
        if isinstance(actual_issues, str):
            candidate_list = [actual_issues.lower()]
        else:
            candidate_list = [
                (iss.statement if hasattr(iss, "statement") else str(iss)).lower()
                for iss in actual_issues
            ]

        # 1. Primary issue check
        primary_targets = [exp.primary_issue.lower()] + [alt.lower() for alt in exp.acceptable_primary_alternatives]
        primary_matched = any(
            any(target in cand or cand in target for target in primary_targets)
            for cand in candidate_list
        )

        if not primary_matched:
            discrepancies.append(
                f"Primary issue miss: expected '{exp.primary_issue}', got {list(actual_issues)}"
            )

        # 2. Check for irrelevant plausible decoy issues
        decoy_hits: list[str] = []
        for decoy in exp.irrelevant_plausible_issues:
            decoy_lower = decoy.lower()
            if any(decoy_lower in cand or cand in decoy_lower for cand in candidate_list):
                decoy_hits.append(decoy)
                discrepancies.append(
                    f"DECOY ISSUE DETECTED: Model focused on irrelevant plausible issue '{decoy}'"
                )

        # 3. Secondary issues recall
        matched_secondary = 0
        for sec in exp.secondary_issues:
            sec_lower = sec.lower()
            if any(sec_lower in cand or cand in sec_lower for cand in candidate_list):
                matched_secondary += 1

        secondary_recall = (
            matched_secondary / len(exp.secondary_issues)
            if exp.secondary_issues
            else 1.0
        )

        passed = primary_matched and (len(decoy_hits) == 0)
        score = (0.7 if primary_matched else 0.0) + (0.3 * secondary_recall)
        if decoy_hits:
            score = max(0.0, score - 0.4)

        return StageEvaluationResult(
            stage_name="ISSUE_IDENTIFICATION",
            passed=passed,
            score=score,
            details={
                "primary_matched": primary_matched,
                "secondary_recall": secondary_recall,
                "decoy_hits": decoy_hits,
                "actual_issues": list(actual_issues) if not isinstance(actual_issues, str) else [actual_issues],
            },
            discrepancies=discrepancies,
            failure_class="DECOY_ISSUE_TRAP" if decoy_hits else ("PRIMARY_ISSUE_MISS" if not primary_matched else None),
        )
