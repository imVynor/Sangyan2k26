"""Causal failure classification for SANGYAN benchmark cases (Phase 7B).

Assigns the EARLIEST causal failure in the pipeline rather than collapsing
everything into a status mismatch. Generic, case-agnostic rules only.
"""

from enum import Enum
from typing import Any


class CausalFailure(str, Enum):
    OPERATIONAL_FAILURE = "OPERATIONAL_FAILURE"
    FACT_EXTRACTION_FAILURE = "FACT_EXTRACTION_FAILURE"
    CORPUS_GAP = "CORPUS_GAP"
    QUERY_FORMULATION_GAP = "QUERY_FORMULATION_GAP"
    TEMPORAL_GAP = "TEMPORAL_GAP"
    AUTHORITY_GAP = "AUTHORITY_GAP"
    RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
    EVIDENCE_MAPPING_GAP = "EVIDENCE_MAPPING_GAP"
    ASSESSMENT_GAP = "ASSESSMENT_GAP"
    EVALUATOR_FAILURE = "EVALUATOR_FAILURE"
    OTHER = "OTHER"


def classify_causal_failure(
    *,
    passed: bool,
    operational_error: str | None,
    stages: dict[str, Any],
    retrieval_stats: dict[str, Any],
    retrieval_result_count: int,
    expected_provision_count: int,
    blocked_by_corpus_gap: bool,
    failure_reasons: list[str],
) -> CausalFailure | None:
    """Return earliest causal failure, or None if the case passed."""
    if passed:
        return None
    if operational_error:
        return CausalFailure.OPERATIONAL_FAILURE

    def failed(name: str) -> bool:
        s = stages.get(name)
        return s is not None and not s.passed

    if failed("FACT_EXTRACTION"):
        return CausalFailure.FACT_EXTRACTION_FAILURE

    if expected_provision_count > 0 and not blocked_by_corpus_gap and failed("PROVISION_RETRIEVAL"):
        # Nothing came back from any channel => query did not reach the corpus.
        total_cands = int(retrieval_stats.get("candidate_count", 0) or 0)
        if retrieval_result_count == 0 or total_cands == 0:
            return CausalFailure.QUERY_FORMULATION_GAP
        fc = stages["PROVISION_RETRIEVAL"].failure_class
        if fc == "TEMPORAL_MISS" or failed("TEMPORAL_REASONING"):
            return CausalFailure.TEMPORAL_GAP
        if fc == "AUTHORITY_MISS":
            return CausalFailure.AUTHORITY_GAP
        if fc == "QUERY_FORMULATION":
            return CausalFailure.QUERY_FORMULATION_GAP
        return CausalFailure.RETRIEVAL_FAILURE

    if failed("EVIDENCE_RESOLUTION"):
        return CausalFailure.EVIDENCE_MAPPING_GAP
    if failed("TEMPORAL_REASONING"):
        return CausalFailure.TEMPORAL_GAP
    if failed("ASSESSMENT"):
        if blocked_by_corpus_gap or "CORPUS_GAP" in failure_reasons:
            return CausalFailure.CORPUS_GAP
        return CausalFailure.ASSESSMENT_GAP
    if failed("CLARIFICATION") or failed("GROUNDING"):
        return CausalFailure.OTHER
    return CausalFailure.OTHER
