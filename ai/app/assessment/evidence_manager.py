"""Evidence Management and Requirement Verification for SANGYAN.

Epistemic foundation:
- An evidence item represents an observed empirical claim.
- Disagreement between multiple evidence sources produces CONTRADICTED, not arbitrary arbitration.
- Tracks required vs known vs missing evidence.
- Retains full provenance chain for every observed value.
"""

from collections import defaultdict
from decimal import Decimal
import logging
from typing import Any, Sequence

from ai.app.assessment.contracts import (
    EvidenceItem,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    EvidenceType,
    ThreeValuedLogic,
)

logger = logging.getLogger("sangyan.assessment.evidence_manager")


class EvidenceManager:
    """Manages case evidence items and evaluates evidence requirements."""

    def __init__(
        self,
        evidence_items: Sequence[EvidenceItem] | None = None,
        resolver: Any = None,
        use_policy: bool = False,
    ) -> None:
        self.items: list[EvidenceItem] = list(evidence_items or [])
        self._by_field: dict[str, list[EvidenceItem]] = defaultdict(list)
        for item in self.items:
            self._by_field[item.field_name].append(item)
        from ai.app.evidence_policy.resolver import EvidencePolicyResolver
        self.resolver = resolver or EvidencePolicyResolver.default()
        self.use_policy = use_policy

    def add_item(self, item: EvidenceItem) -> None:
        """Add a single evidence item."""
        self.items.append(item)
        self._by_field[item.field_name].append(item)

    def get_field_value(
        self,
        field_name: str,
        prefer_documentary: bool = False,
    ) -> tuple[Any, EvidenceRequirementStatus, list[str]]:
        """Retrieve resolved value, status, and supporting evidence IDs for a field.
        
        Returns:
            (value, status, evidence_ids)
        """
        items = self._by_field.get(field_name, [])
        if not items:
            return None, EvidenceRequirementStatus.MISSING, []

        ev_ids = [item.evidence_id for item in items]
        if len(items) == 1:
            return items[0].value, EvidenceRequirementStatus.KNOWN, ev_ids

        if prefer_documentary or self.use_policy:
            from ai.app.evidence_policy.contracts import ClaimStatus
            resolved = self.resolver.resolve_field(field_name, items)
            if resolved.status in {
                ClaimStatus.SUPPORTED,
                ClaimStatus.RESOLVED_BY_POLICY,
                ClaimStatus.RESOLVED_BY_ADDITIONAL_EVIDENCE,
            }:
                supporting_items = [
                    item for item in items
                    if self._values_equal(item.value, resolved.operative_value)
                ]
                supporting_ids = [i.evidence_id for i in supporting_items] or ev_ids
                return resolved.operative_value, EvidenceRequirementStatus.KNOWN, supporting_ids
            elif resolved.status == ClaimStatus.CONTRADICTED:
                return None, EvidenceRequirementStatus.CONTRADICTED, ev_ids

        # Multiple items without documentary precedence: check for raw contradiction
        first_val = items[0].value
        for item in items[1:]:
            if not self._values_equal(first_val, item.value):
                logger.warning(f"Contradiction detected for field '{field_name}': {first_val} vs {item.value}")
                return None, EvidenceRequirementStatus.CONTRADICTED, ev_ids

        return first_val, EvidenceRequirementStatus.KNOWN, ev_ids

    def evaluate_requirements(
        self,
        required_fields: Sequence[str | EvidenceRequirement],
        prefer_documentary: bool = False,
    ) -> list[EvidenceRequirement]:
        """Evaluate a list of required fields against available evidence."""
        results: list[EvidenceRequirement] = []
        for req in required_fields:
            if isinstance(req, str):
                field_name = req
                description = None
            else:
                field_name = req.field_name
                description = req.description

            val, status, ev_ids = self.get_field_value(field_name, prefer_documentary=prefer_documentary)
            results.append(
                EvidenceRequirement(
                    field_name=field_name,
                    description=description,
                    status=status,
                    evidence_ids=ev_ids,
                )
            )
        return results

    def get_missing_fields(
        self,
        required_fields: Sequence[str | EvidenceRequirement],
        prefer_documentary: bool = False,
    ) -> list[str]:
        """Return list of fields that are MISSING or CONTRADICTED."""
        evaluated = self.evaluate_requirements(required_fields, prefer_documentary=prefer_documentary)
        return [
            e.field_name
            for e in evaluated
            if e.status in {EvidenceRequirementStatus.MISSING, EvidenceRequirementStatus.CONTRADICTED}
        ]

    def has_all_requirements(
        self,
        required_fields: Sequence[str | EvidenceRequirement],
    ) -> bool:
        """Check if all required fields are KNOWN."""
        evaluated = self.evaluate_requirements(required_fields)
        return all(e.status == EvidenceRequirementStatus.KNOWN for e in evaluated)

    @staticmethod
    def _values_equal(val1: Any, val2: Any) -> bool:
        """Equivalence check with Decimal / string normalization."""
        if val1 == val2:
            return True
        # Try decimal conversion
        try:
            d1 = Decimal(str(val1).replace("₹", "").replace("Rs", "").strip())
            d2 = Decimal(str(val2).replace("₹", "").replace("Rs", "").strip())
            return d1 == d2
        except Exception:
            pass
        # Normalized string compare
        if isinstance(val1, str) and isinstance(val2, str):
            return val1.strip().lower() == val2.strip().lower()
        return False
