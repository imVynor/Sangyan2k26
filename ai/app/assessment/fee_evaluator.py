"""Deterministic Fee and Charge Evaluator for SANGYAN using Decimal Arithmetic.

Epistemic foundation:
- Money calculations must use Decimal, never binary floating-point arithmetic.
- Supports tariff structures: fixed_fee, percentage, maximum_fee, minimum_fee, conditional_fee, tiered_fee, transaction_based_fee.
- Compares charged amount against permitted maximum/fixed rate.
- Never silently rounds a disputed amount.
- Explicitly flags unknown parameters as UNKNOWN.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from enum import Enum
import logging
from typing import Any
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import ThreeValuedLogic

logger = logging.getLogger("sangyan.assessment.fee_evaluator")


class FeeType(str, Enum):
    """Supported tariff computation models."""
    FIXED_FEE = "fixed_fee"
    PERCENTAGE = "percentage"
    MAXIMUM_FEE = "maximum_fee"
    MINIMUM_FEE = "minimum_fee"
    CONDITIONAL_FEE = "conditional_fee"
    TIERED_FEE = "tiered_fee"
    TRANSACTION_BASED_FEE = "transaction_based_fee"


class FeeEvaluationResult(BaseModel):
    """Audit result of fee calculation and compliance assessment."""
    fee_type: FeeType
    currency: str = "INR"
    charged_amount: Decimal
    permitted_amount: Decimal | None = None
    excess_amount: Decimal | None = None
    is_compliant: ThreeValuedLogic = ThreeValuedLogic.UNKNOWN
    exceeds_permitted: ThreeValuedLogic = ThreeValuedLogic.UNKNOWN
    rounding_mode: str = "ROUND_HALF_UP"
    precision: int = 2
    formula_description: str
    notes: str | None = None


class FeeEvaluator:
    """Evaluates fees and financial charges deterministically using Decimal."""

    @staticmethod
    def to_decimal(val: Any) -> Decimal:
        """Coerce value to Decimal without float conversion artifacts."""
        if isinstance(val, Decimal):
            return val
        if isinstance(val, (int, str)):
            cleaned = str(val).replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
            return Decimal(cleaned)
        if isinstance(val, float):
            return Decimal(str(val))
        raise ValueError(f"Cannot convert {val} of type {type(val)} to Decimal.")

    @classmethod
    def evaluate_fixed_fee(
        cls,
        charged: Any,
        permitted_fixed: Any,
        currency: str = "INR",
        tolerance: Decimal = Decimal("0.00"),
    ) -> FeeEvaluationResult:
        """Evaluate fixed fee (e.g. DP charge ₹13.50 + GST)."""
        d_charged = cls.to_decimal(charged)
        d_permitted = cls.to_decimal(permitted_fixed)

        diff = d_charged - d_permitted
        if diff > tolerance:
            exceeds = ThreeValuedLogic.TRUE
            compliant = ThreeValuedLogic.FALSE
        else:
            exceeds = ThreeValuedLogic.FALSE
            compliant = ThreeValuedLogic.TRUE

        return FeeEvaluationResult(
            fee_type=FeeType.FIXED_FEE,
            currency=currency,
            charged_amount=d_charged,
            permitted_amount=d_permitted,
            excess_amount=max(Decimal("0.00"), diff),
            is_compliant=compliant,
            exceeds_permitted=exceeds,
            formula_description=f"Fixed tariff: permitted={d_permitted}, charged={d_charged}",
        )

    @classmethod
    def evaluate_maximum_ceiling(
        cls,
        charged: Any,
        maximum_ceiling: Any,
        currency: str = "INR",
    ) -> FeeEvaluationResult:
        """Evaluate statutory ceiling rule (e.g. fee <= ₹20)."""
        d_charged = cls.to_decimal(charged)
        d_max = cls.to_decimal(maximum_ceiling)

        if d_charged > d_max:
            exceeds = ThreeValuedLogic.TRUE
            compliant = ThreeValuedLogic.FALSE
            excess = d_charged - d_max
        else:
            exceeds = ThreeValuedLogic.FALSE
            compliant = ThreeValuedLogic.TRUE
            excess = Decimal("0.00")

        return FeeEvaluationResult(
            fee_type=FeeType.MAXIMUM_FEE,
            currency=currency,
            charged_amount=d_charged,
            permitted_amount=d_max,
            excess_amount=excess,
            is_compliant=compliant,
            exceeds_permitted=exceeds,
            formula_description=f"Maximum ceiling: ceiling={d_max}, charged={d_charged}",
        )

    @classmethod
    def evaluate_percentage_fee(
        cls,
        charged: Any,
        transaction_value: Any,
        percentage_rate: Any,
        maximum_cap: Any | None = None,
        minimum_floor: Any | None = None,
        currency: str = "INR",
        precision: int = 2,
    ) -> FeeEvaluationResult:
        """Evaluate percentage-based fee: max(min(value * rate, cap), floor)."""
        d_charged = cls.to_decimal(charged)
        d_val = cls.to_decimal(transaction_value)
        d_rate = cls.to_decimal(percentage_rate)

        # Rate can be e.g. 0.05% (0.0005) or 0.05
        # If rate > 1, assume expressed as percent (e.g. 18 -> 18%)
        if d_rate > Decimal("1.0"):
            pct = d_rate / Decimal("100")
        else:
            pct = d_rate

        raw_calc = (d_val * pct).quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP)
        permitted = raw_calc

        if minimum_floor is not None:
            d_min = cls.to_decimal(minimum_floor)
            if permitted < d_min:
                permitted = d_min

        if maximum_cap is not None:
            d_cap = cls.to_decimal(maximum_cap)
            if permitted > d_cap:
                permitted = d_cap

        diff = d_charged - permitted
        if diff > Decimal("0.00"):
            exceeds = ThreeValuedLogic.TRUE
            compliant = ThreeValuedLogic.FALSE
            excess = diff
        else:
            exceeds = ThreeValuedLogic.FALSE
            compliant = ThreeValuedLogic.TRUE
            excess = Decimal("0.00")

        return FeeEvaluationResult(
            fee_type=FeeType.PERCENTAGE,
            currency=currency,
            charged_amount=d_charged,
            permitted_amount=permitted,
            excess_amount=excess,
            is_compliant=compliant,
            exceeds_permitted=exceeds,
            precision=precision,
            formula_description=(
                f"Percentage: {pct*100}% on {d_val} = {raw_calc}"
                f"{f', cap={maximum_cap}' if maximum_cap else ''}"
                f"{f', floor={minimum_floor}' if minimum_floor else ''}"
            ),
        )

    @classmethod
    def evaluate_tiered_fee(
        cls,
        charged: Any,
        turnover_or_tier_key: Any,
        tiers: list[dict[str, Any]],
        currency: str = "INR",
    ) -> FeeEvaluationResult:
        """Evaluate tiered fee table.
        Each tier has e.g.: {'max_amount': Decimal('100000'), 'rate': Decimal('15')}
        """
        d_charged = cls.to_decimal(charged)
        d_key = cls.to_decimal(turnover_or_tier_key)

        selected_tier = None
        for tier in sorted(tiers, key=lambda t: t.get("max_amount", Decimal("Infinity"))):
            tier_max = tier.get("max_amount")
            if tier_max is None or d_key <= cls.to_decimal(tier_max):
                selected_tier = tier
                break

        if selected_tier is None:
            return FeeEvaluationResult(
                fee_type=FeeType.TIERED_FEE,
                currency=currency,
                charged_amount=d_charged,
                is_compliant=ThreeValuedLogic.UNKNOWN,
                exceeds_permitted=ThreeValuedLogic.UNKNOWN,
                formula_description=f"No matching tier found for value {d_key}",
            )

        permitted = cls.to_decimal(selected_tier["rate"])
        diff = d_charged - permitted
        if diff > Decimal("0.00"):
            exceeds = ThreeValuedLogic.TRUE
            compliant = ThreeValuedLogic.FALSE
            excess = diff
        else:
            exceeds = ThreeValuedLogic.FALSE
            compliant = ThreeValuedLogic.TRUE
            excess = Decimal("0.00")

        return FeeEvaluationResult(
            fee_type=FeeType.TIERED_FEE,
            currency=currency,
            charged_amount=d_charged,
            permitted_amount=permitted,
            excess_amount=excess,
            is_compliant=compliant,
            exceeds_permitted=exceeds,
            formula_description=f"Tiered fee: tier_max={selected_tier.get('max_amount')}, permitted={permitted}",
        )
