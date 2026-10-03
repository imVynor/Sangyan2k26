"""Deterministic Condition Evaluator with Three-Valued Logic for SANGYAN.

Epistemic invariants:
- Supports Kleene Three-Valued Logic: TRUE, FALSE, UNKNOWN.
- Never treat UNKNOWN as FALSE. Never treat UNKNOWN as TRUE.
- Strictly NO Python eval() or dynamic code execution.
- Monetary and numerical values are coerced to Decimal to eliminate binary float rounding errors.
- Clean AST/operator dispatch for date, numerical, collection, and equality predicates.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import logging
from typing import Any

from ai.app.assessment.contracts import (
    ConditionEvaluation,
    ConditionOperator,
    ThreeValuedLogic,
)

logger = logging.getLogger("sangyan.assessment.condition_evaluator")


def _to_decimal(val: Any) -> Decimal | None:
    """Safely convert value to Decimal, stripping currency symbols and formatting."""
    if val is None or val == "UNKNOWN":
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    if isinstance(val, str):
        cleaned = val.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


def _to_date(val: Any) -> date | None:
    """Safely convert string or datetime to date."""
    if val is None or val == "UNKNOWN":
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        cleaned = val.strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
    return None


class ConditionEvaluator:
    """Evaluates predicate conditions against observed case facts deterministically."""

    @staticmethod
    def evaluate(
        condition_id: str,
        field: str,
        operator: ConditionOperator | str,
        target_value: Any,
        observed_value: Any,
        evidence_ids: list[str] | None = None,
    ) -> ConditionEvaluation:
        """Evaluate a condition against an observed value using Three-Valued Logic."""
        if isinstance(operator, str):
            try:
                op_enum = ConditionOperator(operator)
            except ValueError:
                return ConditionEvaluation(
                    condition_id=condition_id,
                    field=field,
                    operator=ConditionOperator.EQUALS,
                    target_value=target_value,
                    observed_value=observed_value,
                    result=ThreeValuedLogic.UNKNOWN,
                    evidence_ids=evidence_ids or [],
                    derived_reason=f"Unsupported operator: {operator}",
                )
        else:
            op_enum = operator

        ev_ids = evidence_ids or []

        # If observed value is missing, None, or UNKNOWN, result is strictly UNKNOWN
        if observed_value is None or observed_value == "UNKNOWN":
            return ConditionEvaluation(
                condition_id=condition_id,
                field=field,
                operator=op_enum,
                target_value=target_value,
                observed_value=observed_value,
                result=ThreeValuedLogic.UNKNOWN,
                evidence_ids=ev_ids,
                derived_reason=f"Field '{field}' is missing or unknown in case evidence.",
            )

        # Dispatch operator
        try:
            if op_enum == ConditionOperator.EQUALS:
                res = ConditionEvaluator._eval_equals(observed_value, target_value)
            elif op_enum == ConditionOperator.NOT_EQUALS:
                res = ~ConditionEvaluator._eval_equals(observed_value, target_value)
            elif op_enum in {
                ConditionOperator.GREATER_THAN,
                ConditionOperator.LESS_THAN,
                ConditionOperator.GREATER_OR_EQUAL,
                ConditionOperator.LESS_OR_EQUAL,
            }:
                res = ConditionEvaluator._eval_numerical_comp(op_enum, observed_value, target_value)
            elif op_enum == ConditionOperator.IN:
                res = ConditionEvaluator._eval_in(observed_value, target_value)
            elif op_enum == ConditionOperator.NOT_IN:
                res = ~ConditionEvaluator._eval_in(observed_value, target_value)
            elif op_enum == ConditionOperator.CONTAINS:
                res = ConditionEvaluator._eval_contains(observed_value, target_value)
            elif op_enum in {
                ConditionOperator.DATE_BEFORE,
                ConditionOperator.DATE_AFTER,
                ConditionOperator.DATE_BETWEEN,
            }:
                res = ConditionEvaluator._eval_date_comp(op_enum, observed_value, target_value)
            else:
                res = ThreeValuedLogic.UNKNOWN

            derived_reason = f"Evaluated {field} ({observed_value}) {op_enum.value} {target_value} -> {res.value}"

            return ConditionEvaluation(
                condition_id=condition_id,
                field=field,
                operator=op_enum,
                target_value=target_value,
                observed_value=observed_value,
                result=res,
                evidence_ids=ev_ids,
                derived_reason=derived_reason,
            )

        except Exception as exc:
            logger.warning(f"Error evaluating condition {condition_id}: {exc}")
            return ConditionEvaluation(
                condition_id=condition_id,
                field=field,
                operator=op_enum,
                target_value=target_value,
                observed_value=observed_value,
                result=ThreeValuedLogic.UNKNOWN,
                evidence_ids=ev_ids,
                derived_reason=f"Evaluation error: {exc}",
            )

    @staticmethod
    def _eval_equals(observed: Any, target: Any) -> ThreeValuedLogic:
        # Check decimal comparison first
        d_obs = _to_decimal(observed)
        d_tgt = _to_decimal(target)
        if d_obs is not None and d_tgt is not None:
            return ThreeValuedLogic.TRUE if d_obs == d_tgt else ThreeValuedLogic.FALSE

        # String normalized comparison
        if isinstance(observed, str) and isinstance(target, str):
            return ThreeValuedLogic.TRUE if observed.strip().lower() == target.strip().lower() else ThreeValuedLogic.FALSE

        return ThreeValuedLogic.TRUE if observed == target else ThreeValuedLogic.FALSE

    @staticmethod
    def _eval_numerical_comp(
        op: ConditionOperator,
        observed: Any,
        target: Any,
    ) -> ThreeValuedLogic:
        d_obs = _to_decimal(observed)
        d_tgt = _to_decimal(target)
        if d_obs is None or d_tgt is None:
            return ThreeValuedLogic.UNKNOWN

        if op == ConditionOperator.GREATER_THAN:
            return ThreeValuedLogic.TRUE if d_obs > d_tgt else ThreeValuedLogic.FALSE
        elif op == ConditionOperator.LESS_THAN:
            return ThreeValuedLogic.TRUE if d_obs < d_tgt else ThreeValuedLogic.FALSE
        elif op == ConditionOperator.GREATER_OR_EQUAL:
            return ThreeValuedLogic.TRUE if d_obs >= d_tgt else ThreeValuedLogic.FALSE
        elif op == ConditionOperator.LESS_OR_EQUAL:
            return ThreeValuedLogic.TRUE if d_obs <= d_tgt else ThreeValuedLogic.FALSE
        return ThreeValuedLogic.UNKNOWN

    @staticmethod
    def _eval_in(observed: Any, target: Any) -> ThreeValuedLogic:
        if target is None:
            return ThreeValuedLogic.UNKNOWN
        if isinstance(target, (list, tuple, set)):
            # Normalize strings if applicable
            if isinstance(observed, str):
                obs_norm = observed.strip().lower()
                tgt_norm = {str(item).strip().lower() for item in target}
                return ThreeValuedLogic.TRUE if obs_norm in tgt_norm else ThreeValuedLogic.FALSE
            return ThreeValuedLogic.TRUE if observed in target else ThreeValuedLogic.FALSE
        return ThreeValuedLogic.UNKNOWN

    @staticmethod
    def _eval_contains(observed: Any, target: Any) -> ThreeValuedLogic:
        if observed is None or target is None:
            return ThreeValuedLogic.UNKNOWN
        if isinstance(observed, (list, tuple, set)):
            return ThreeValuedLogic.TRUE if target in observed else ThreeValuedLogic.FALSE
        if isinstance(observed, str):
            return ThreeValuedLogic.TRUE if str(target).lower() in observed.lower() else ThreeValuedLogic.FALSE
        return ThreeValuedLogic.UNKNOWN

    @staticmethod
    def _eval_date_comp(
        op: ConditionOperator,
        observed: Any,
        target: Any,
    ) -> ThreeValuedLogic:
        d_obs = _to_date(observed)
        if d_obs is None:
            return ThreeValuedLogic.UNKNOWN

        if op == ConditionOperator.DATE_BEFORE:
            d_tgt = _to_date(target)
            if d_tgt is None:
                return ThreeValuedLogic.UNKNOWN
            return ThreeValuedLogic.TRUE if d_obs < d_tgt else ThreeValuedLogic.FALSE

        elif op == ConditionOperator.DATE_AFTER:
            d_tgt = _to_date(target)
            if d_tgt is None:
                return ThreeValuedLogic.UNKNOWN
            return ThreeValuedLogic.TRUE if d_obs > d_tgt else ThreeValuedLogic.FALSE

        elif op == ConditionOperator.DATE_BETWEEN:
            if isinstance(target, (list, tuple)) and len(target) == 2:
                d_start = _to_date(target[0])
                d_end = _to_date(target[1])
                if d_start is None or d_end is None:
                    return ThreeValuedLogic.UNKNOWN
                return ThreeValuedLogic.TRUE if d_start <= d_obs <= d_end else ThreeValuedLogic.FALSE
            return ThreeValuedLogic.UNKNOWN

        return ThreeValuedLogic.UNKNOWN
