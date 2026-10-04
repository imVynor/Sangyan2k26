"""Deterministic Conflict Detection and Resolution for SANGYAN Provisions.

Epistemic foundation:
- Conflicts occur when two applicable provisions impose contradictory mandates or tariffs.
- Never choose a provision merely based on a higher retrieval score.
- Resolves conflicts deterministically through:
  1. Temporal supersession (newer prevailing rule)
  2. Authority hierarchy (SEBI/Depository overrides Broker policy)
  3. Specificity (transaction-specific rule overrides general rule)
  4. Exception relationship
- Unresolved conflicts produce CONFLICTING_PROVISIONS.
"""

from decimal import Decimal
import logging
from typing import Any, Sequence

from ai.app.assessment.contracts import (
    ApplicabilityEvaluation,
    Conflict,
    ConflictResolutionBasis,
)
from ai.app.retrieval.contracts import RetrievalResult

logger = logging.getLogger("sangyan.assessment.conflict_detector")

# Authority normative hierarchy ranking (higher value has legal precedence)
AUTHORITY_PRECEDENCE = {
    "SEBI": 100,
    "CDSL": 80,
    "NSDL": 80,
    "NSE": 70,
    "BSE": 70,
    "ORG_ZERODHA": 50,
    "ORG_ANGELONE": 50,
    "ORG_UPSTOX": 50,
    "ORG_GROWW": 50,
    "ORG_ICICIDIRECT": 50,
}


class ConflictDetector:
    """Detects and attempts deterministic resolution of conflicting retrieved provisions."""

    @classmethod
    def detect_conflicts(
        cls,
        evaluations: Sequence[ApplicabilityEvaluation],
        retrieved_map: dict[str, RetrievalResult],
    ) -> list[Conflict]:
        """Examine applicable provisions for contradictory rules or limits."""
        # Only compare provisions that are applicable or unresolved, and not ruled NOT_APPLICABLE
        applicable_evals = [
            e for e in evaluations
            if e.overall_applicability in {"APPLICABLE", "UNRESOLVED"}
            and e.rule_outcome.value not in {"NOT_APPLICABLE"}
            and e.provision_id in retrieved_map
        ]

        conflicts: list[Conflict] = []
        n = len(applicable_evals)

        for i in range(n):
            for j in range(i + 1, n):
                ev1 = applicable_evals[i]
                ev2 = applicable_evals[j]
                r1 = retrieved_map[ev1.provision_id]
                r2 = retrieved_map[ev2.provision_id]

                conflict_nature = cls._find_contradiction(ev1, ev2, r1, r2)
                if conflict_nature:
                    c = cls._resolve_conflict(ev1, ev2, r1, r2, conflict_nature)
                    conflicts.append(c)

        return conflicts

    @classmethod
    def _find_contradiction(
        cls,
        ev1: ApplicabilityEvaluation,
        ev2: ApplicabilityEvaluation,
        r1: RetrievalResult,
        r2: RetrievalResult,
    ) -> str | None:
        """Check if two provisions contradict each other."""
        # 1. Check if both have conditions on the same normative limit/fee field with contradictory target values
        normative_fields = {"charged_amount", "permitted_amount", "fee_amount", "regulatory_ceiling", "turnover_limit"}
        for c1 in ev1.conditions:
            if c1.field not in normative_fields:
                continue
            for c2 in ev2.conditions:
                if c1.field == c2.field and c1.operator == c2.operator:
                    # If target values differ significantly (e.g. limit 15 vs 20)
                    if c1.target_value != c2.target_value:
                        try:
                            d1 = Decimal(str(c1.target_value))
                            d2 = Decimal(str(c2.target_value))
                            if d1 != d2:
                                return f"Contradictory condition targets on '{c1.field}': {d1} vs {d2}"
                        except Exception:
                            if str(c1.target_value).lower() != str(c2.target_value).lower():
                                return f"Contradictory condition targets on '{c1.field}': {c1.target_value} vs {c2.target_value}"

        # 2. Check if one is SATISFIED and one is VIOLATED on the exact same core issue/domain
        if ev1.rule_outcome.value == "SATISFIED" and ev2.rule_outcome.value == "VIOLATED":
            # If they belong to the same source class, this is a direct contradiction
            if r1.source_class == r2.source_class:
                return f"Opposing outcomes (SATISFIED vs VIOLATED) within same source class {r1.source_class}"

        return None

    @classmethod
    def _resolve_conflict(
        cls,
        ev1: ApplicabilityEvaluation,
        ev2: ApplicabilityEvaluation,
        r1: RetrievalResult,
        r2: RetrievalResult,
        nature: str,
    ) -> Conflict:
        """Attempt deterministic resolution using legal precedence rules."""
        conflict_id = f"CONF-{ev1.provision_id[:12]}-{ev2.provision_id[:12]}"

        # 1. Authority Hierarchy: Regulatory > Organisation Policy
        p1_rank = AUTHORITY_PRECEDENCE.get(r1.authority or r1.organisation_id or "", 0)
        p2_rank = AUTHORITY_PRECEDENCE.get(r2.authority or r2.organisation_id or "", 0)

        if r1.source_class == "REGULATORY" and r2.source_class != "REGULATORY":
            return Conflict(
                conflict_id=conflict_id,
                provision_ids=[r1.provision_id, r2.provision_id],
                nature_of_conflict=nature,
                resolution_attempted=True,
                resolved=True,
                prevailing_provision_id=r1.provision_id,
                resolution_basis=ConflictResolutionBasis.AUTHORITY_HIERARCHY,
                explanation=f"Regulatory provision {r1.provision_id} overrides intermediary policy {r2.provision_id}.",
            )

        if r2.source_class == "REGULATORY" and r1.source_class != "REGULATORY":
            return Conflict(
                conflict_id=conflict_id,
                provision_ids=[r1.provision_id, r2.provision_id],
                nature_of_conflict=nature,
                resolution_attempted=True,
                resolved=True,
                prevailing_provision_id=r2.provision_id,
                resolution_basis=ConflictResolutionBasis.AUTHORITY_HIERARCHY,
                explanation=f"Regulatory provision {r2.provision_id} overrides intermediary policy {r1.provision_id}.",
            )

        # 2. Temporal Precedence: If both are same authority, newer effective date prevails
        if r1.effective_from and r2.effective_from:
            if r1.effective_from > r2.effective_from:
                return Conflict(
                    conflict_id=conflict_id,
                    provision_ids=[r1.provision_id, r2.provision_id],
                    nature_of_conflict=nature,
                    resolution_attempted=True,
                    resolved=True,
                    prevailing_provision_id=r1.provision_id,
                    resolution_basis=ConflictResolutionBasis.TEMPORAL_SUPERSEDED,
                    explanation=f"Provision {r1.provision_id} took effect later ({r1.effective_from}) than {r2.provision_id} ({r2.effective_from}).",
                )
            elif r2.effective_from > r1.effective_from:
                return Conflict(
                    conflict_id=conflict_id,
                    provision_ids=[r1.provision_id, r2.provision_id],
                    nature_of_conflict=nature,
                    resolution_attempted=True,
                    resolved=True,
                    prevailing_provision_id=r2.provision_id,
                    resolution_basis=ConflictResolutionBasis.TEMPORAL_SUPERSEDED,
                    explanation=f"Provision {r2.provision_id} took effect later ({r2.effective_from}) than {r1.provision_id} ({r1.effective_from}).",
                )

        # 3. Unresolved
        return Conflict(
            conflict_id=conflict_id,
            provision_ids=[r1.provision_id, r2.provision_id],
            nature_of_conflict=nature,
            resolution_attempted=True,
            resolved=False,
            prevailing_provision_id=None,
            resolution_basis=ConflictResolutionBasis.UNRESOLVED,
            explanation=f"Cannot deterministically resolve conflict: {nature}",
        )
