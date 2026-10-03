"""Case Fact Integration and Proposal Validation Boundary for SANGYAN.

Epistemic foundation:
- Extraction produces PROPOSALS (candidate facts), never directly mutating authoritative case state.
- Validates candidate facts before admitting them into CaseState and EvidenceManager.
- Resolves conflicts or records contradictions when multiple sources disagree.
- Preserves full auditability between raw extraction proposals and committed case state.
"""

from decimal import Decimal
import logging
from typing import Any

from ai.app.assessment.contracts import EvidenceItem
from ai.app.extraction.contracts import FactExtractionResult, FactEpistemicStatus

logger = logging.getLogger("sangyan.extraction.case_integrator")


class CaseIntegrator:
    """Safely mediates between candidate extraction proposals and committed case state."""

    @classmethod
    def integrate_proposals(
        cls,
        extraction_result: FactExtractionResult,
        case_id: str,
        existing_evidence: list[EvidenceItem] | None = None,
        existing_facts: dict[str, Any] | None = None,
    ) -> tuple[list[EvidenceItem], dict[str, Any], list[str]]:
        """Validate and integrate candidate proposals into confirmed evidence and case facts.
        
        Returns:
            (committed_evidence_items, committed_case_facts, integration_warnings)
        """
        committed_evidence: list[EvidenceItem] = list(existing_evidence or [])
        committed_facts: dict[str, Any] = dict(existing_facts or {})
        warnings: list[str] = list(extraction_result.extraction_warnings)

        # Flag any internal contradictions from the extraction
        if extraction_result.contradictions:
            warnings.extend(extraction_result.contradictions)

        # Process each evidence proposal
        for prop in extraction_result.evidence_proposals:
            # Bind to actual case_id
            prop.case_id = case_id
            committed_evidence.append(prop)

        # Process candidate case facts
        for field, cand_val in extraction_result.case_fact_candidates.items():
            if field in committed_facts:
                existing_val = committed_facts[field]
                if not cls._facts_match(existing_val, cand_val):
                    warning_msg = (
                        f"Conflict for field '{field}': existing committed value '{existing_val}' "
                        f"conflicts with newly extracted candidate '{cand_val}'."
                    )
                    logger.warning(warning_msg)
                    warnings.append(warning_msg)
                    # When conflict occurs, do NOT overwrite; keep existing and preserve conflict in warnings
                    continue
            committed_facts[field] = cand_val

        return committed_evidence, committed_facts, warnings

    @staticmethod
    def _facts_match(val1: Any, val2: Any) -> bool:
        """Deterministic equivalence check for facts."""
        if val1 == val2:
            return True
        try:
            d1 = Decimal(str(val1).replace("₹", "").strip())
            d2 = Decimal(str(val2).replace("₹", "").strip())
            return d1 == d2
        except Exception:
            pass
        if isinstance(val1, str) and isinstance(val2, str):
            return val1.strip().lower() == val2.strip().lower()
        return False
