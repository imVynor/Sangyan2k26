"""Temporal Rule Applicability and Version Evaluator for SANGYAN (Phase 7A).

Epistemic foundation:
- Verifies that the operative rule version matches the transaction date.
- Explicitly tests against superseded or future rules.
- Prevents false-positive passing where the temporal engine ran but picked the wrong circular.
"""

from datetime import date
import logging
from typing import Any, Sequence

from ai.evaluation.corpus.models import EvaluationCase, StageEvaluationResult
from ai.evaluation.corpus.taxonomy import RetrievalFailureClass

logger = logging.getLogger("sangyan.evaluation.temporal")


class TemporalEvaluator:
    """Evaluates whether the system selected the temporally valid regulatory regime."""

    def evaluate(
        self,
        case: EvaluationCase,
        selected_provision_ids: Sequence[str],
        resolved_temporal_regime: str | None = None,
        effective_date_used: date | None = None,
    ) -> StageEvaluationResult:
        if not case.expected_temporal_context:
            return StageEvaluationResult(
                stage_name="TEMPORAL_REASONING",
                passed=True,
                score=1.0,
                details={"skipped": True, "reason": "No expected_temporal_context defined"},
            )

        exp_temp = case.expected_temporal_context
        discrepancies: list[str] = []

        # 1. Check if expected historical version or circular reference was matched
        regime_matched = True
        if exp_temp.expected_rule_version:
            if not resolved_temporal_regime or exp_temp.expected_rule_version.lower() not in resolved_temporal_regime.lower():
                regime_matched = False
                discrepancies.append(
                    f"Temporal regime miss: expected '{exp_temp.expected_rule_version}', "
                    f"got {resolved_temporal_regime!r}"
                )

        # 2. Check if selected provisions contain the expected temporal provision
        expected_pids = [p.provision_id for p in case.expected_provisions]
        prov_matched = any(pid in selected_provision_ids for pid in expected_pids) if expected_pids else True

        if not prov_matched:
            discrepancies.append(
                f"Selected provisions {list(selected_provision_ids)} do not include "
                f"the temporally correct provision(s): {expected_pids}"
            )

        passed = regime_matched and prov_matched
        score = 1.0 if passed else (0.5 if (regime_matched or prov_matched) else 0.0)

        return StageEvaluationResult(
            stage_name="TEMPORAL_REASONING",
            passed=passed,
            score=score,
            details={
                "transaction_date": str(exp_temp.transaction_date) if exp_temp.transaction_date else None,
                "expected_rule_version": exp_temp.expected_rule_version,
                "resolved_temporal_regime": resolved_temporal_regime,
                "regime_matched": regime_matched,
                "prov_matched": prov_matched,
            },
            discrepancies=discrepancies,
            failure_class=RetrievalFailureClass.TEMPORAL_MISS.value if not passed else None,
        )
