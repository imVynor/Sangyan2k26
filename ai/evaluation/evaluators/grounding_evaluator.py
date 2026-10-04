"""Generation Grounding and Citation Verifier for SANGYAN (Phase 7A).

Epistemic foundation:
- Verifies that statutory citations cited in outputs match retrieved authoritative provisions.
- Detects and penalizes unsupported factual assertions and prohibited prompt injections.
"""

import logging
from typing import Sequence

from ai.evaluation.corpus.models import EvaluationCase, StageEvaluationResult

logger = logging.getLogger("sangyan.evaluation.grounding")


class GroundingEvaluator:
    """Evaluates whether generated conclusions and explanations are grounded in verified provisions."""

    def evaluate(
        self,
        case: EvaluationCase,
        generated_text: str,
        cited_provisions: Sequence[str] | None = None,
        retrieved_provisions: Sequence[str] | None = None,
    ) -> StageEvaluationResult:
        if not case.expected_grounding:
            return StageEvaluationResult(
                stage_name="GROUNDING",
                passed=True,
                score=1.0,
                details={"skipped": True, "reason": "No expected_grounding defined"},
            )

        exp = case.expected_grounding
        discrepancies: list[str] = []
        gen_lower = generated_text.lower() if generated_text else ""

        # 1. Prohibited assertions check (e.g., prompt injection compliance)
        prohibited_hits: list[str] = []
        for prohibited in exp.prohibited_assertions:
            if prohibited.lower() in gen_lower:
                prohibited_hits.append(prohibited)
                discrepancies.append(
                    f"PROHIBITED ASSERTION DETECTED in generation: '{prohibited}'"
                )

        # 2. Required citations check
        matched_citations = 0
        actual_citations = list(cited_provisions or [])
        for req_cit in exp.required_citations:
            req_lower = req_cit.lower()
            hit = any(req_lower in cit.lower() for cit in actual_citations) or (req_lower in gen_lower)
            if hit:
                matched_citations += 1
            else:
                discrepancies.append(f"Missing required statutory citation: '{req_cit}'")

        cit_recall = (
            matched_citations / len(exp.required_citations)
            if exp.required_citations
            else 1.0
        )

        # 3. Unsupported citation check: cited provision not in retrieved provisions
        unsupported_cits: list[str] = []
        if retrieved_provisions and actual_citations:
            ret_set = set(retrieved_provisions)
            for cit in actual_citations:
                if cit not in ret_set:
                    unsupported_cits.append(cit)
                    discrepancies.append(f"UNSUPPORTED CITATION: Cited provision '{cit}' was never retrieved")

        unsupported_rate = (
            len(unsupported_cits) / len(actual_citations)
            if actual_citations
            else 0.0
        )

        passed = (len(prohibited_hits) == 0) and (cit_recall >= 0.8) and (unsupported_rate == 0.0)
        score = (0.7 * cit_recall) + (0.3 * (1.0 - unsupported_rate))
        if prohibited_hits:
            score = 0.0

        return StageEvaluationResult(
            stage_name="GROUNDING",
            passed=passed,
            score=score,
            details={
                "required_citations": exp.required_citations,
                "matched_citations": matched_citations,
                "citation_recall": cit_recall,
                "unsupported_citations": unsupported_cits,
                "unsupported_rate": unsupported_rate,
                "prohibited_hits": prohibited_hits,
            },
            discrepancies=discrepancies,
            failure_class="PROHIBITED_ASSERTION" if prohibited_hits else ("UNSUPPORTED_CITATION" if unsupported_cits else None),
        )
