"""Fact Extraction and Epistemic Unknown Evaluator for SANGYAN (Phase 7A).

Epistemic foundation:
- Evaluates fact extraction precision, recall, and typed value accuracy.
- Enforces exact Decimal comparison with optional absolute tolerance.
- Penalizes hallucinated facts: any fact designated as an ExpectedUnknown that is
  extracted with a non-null value triggers a negative invariant failure.
"""

from decimal import Decimal
import logging
from typing import Any, Mapping

from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedFact,
    ExpectedUnknown,
    StageEvaluationResult,
)

logger = logging.getLogger("sangyan.evaluation.fact")


class FactEvaluator:
    """Evaluates extracted empirical facts against gold expectations."""

    def evaluate(
        self,
        case: EvaluationCase,
        actual_facts: Mapping[str, Any],
    ) -> StageEvaluationResult:
        """Compare actual extracted facts against expected facts and unknowns."""
        discrepancies: list[str] = []
        matched_facts = 0
        total_expected = len(case.expected_facts)

        # 1. Evaluate expected facts
        for ef in case.expected_facts:
            field = ef.field
            if field not in actual_facts or actual_facts[field] is None:
                if ef.required:
                    discrepancies.append(f"Missing required fact: '{field}' (expected: {ef.expected_value})")
                continue

            actual_val = actual_facts[field]
            val_match = self._values_match(ef.expected_value, actual_val, ef.tolerance)

            if val_match:
                matched_facts += 1
            else:
                discrepancies.append(
                    f"Fact mismatch for '{field}': expected {ef.expected_value!r} ({type(ef.expected_value).__name__}), "
                    f"got {actual_val!r} ({type(actual_val).__name__})"
                )

        # 2. Evaluate negative unknowns (hallucination penalty)
        hallucinated_facts = 0
        for unk in case.expected_unknowns:
            field = unk.field
            if field in actual_facts and actual_facts[field] is not None:
                actual_val = actual_facts[field]
                hallucinated_facts += 1
                discrepancies.append(
                    f"HALLUCINATION: Fact '{field}' was expected to remain unknown/null, "
                    f"but was extracted as {actual_val!r} (Reason: {unk.reason})"
                )

        fact_accuracy = (matched_facts / total_expected) if total_expected > 0 else 1.0
        passed = (len(discrepancies) == 0) and (hallucinated_facts == 0)

        return StageEvaluationResult(
            stage_name="FACT_EXTRACTION",
            passed=passed,
            score=fact_accuracy if hallucinated_facts == 0 else max(0.0, fact_accuracy - 0.5),
            details={
                "total_expected": total_expected,
                "matched_facts": matched_facts,
                "total_unknowns": len(case.expected_unknowns),
                "hallucinated_facts": hallucinated_facts,
                "fact_accuracy": fact_accuracy,
            },
            discrepancies=discrepancies,
            failure_class="HALLUCINATED_FACT" if hallucinated_facts > 0 else ("FACT_EXTRACTION_MISS" if not passed else None),
        )

    def _values_match(self, expected: Any, actual: Any, tolerance: Decimal | None) -> bool:
        """Check equality with support for Decimal, dates, and strings."""
        if expected is None and actual is None:
            return True
        if expected is None or actual is None:
            return False

        # Numeric Decimal comparison
        if isinstance(expected, Decimal) or isinstance(actual, Decimal):
            try:
                exp_dec = Decimal(str(expected))
                act_dec = Decimal(str(actual))
                if tolerance is not None:
                    return abs(exp_dec - act_dec) <= tolerance
                return exp_dec == act_dec
            except Exception:
                return False

        # Float/int fallback
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if tolerance is not None:
                return abs(Decimal(str(expected)) - Decimal(str(actual))) <= tolerance
            return expected == actual

        # String normalization
        if isinstance(expected, str) and isinstance(actual, str):
            return expected.strip().lower() == actual.strip().lower()

        return str(expected).strip().lower() == str(actual).strip().lower()
