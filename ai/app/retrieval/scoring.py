"""Hybrid Scoring, Authority Relevance, and Temporal Validation.

Epistemic foundation:
- Separate Relevance from Applicability: a rule can be highly relevant but expired, or moderately relevant and active.
- Configurable weights and normalization prevents any single channel from dominating.
- Distinguishes regulatory authority from intermediary policy without crude "regulatory always wins" suppression.
"""

from datetime import date
import logging
from typing import Sequence

from ai.app.knowledge.provisions import Provision
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import SupersededStatus, TemporalResolutionState, TemporalScope
from ai.app.knowledge.temporal_engine import TemporalApplicabilityEngine
from ai.app.retrieval.contracts import (
    HybridRetrievalConfig,
    RetrievalCandidate,
    RetrievalMode,
    RetrievalQuery,
)

logger = logging.getLogger("sangyan.retrieval.scoring")


class HybridScorer:
    """Combines multi-channel scores and evaluates authority and temporal applicability."""

    def __init__(
        self,
        config: HybridRetrievalConfig | None = None,
        temporal_engine: TemporalApplicabilityEngine | None = None,
    ) -> None:
        self.config = config or HybridRetrievalConfig()
        self.temporal_engine = temporal_engine or TemporalApplicabilityEngine()

    def score_and_validate(
        self,
        candidates: list[RetrievalCandidate],
        query: RetrievalQuery,
        routed_authorities: list[str],
        routed_organisations: list[str],
    ) -> list[RetrievalCandidate]:
        """Compute hybrid relevance score, authority score, and temporal applicability status."""
        eval_date = query.incident_date if query.mode == RetrievalMode.HISTORICAL_RULES else (query.reference_date or date.today())

        for c in candidates:
            # 1. Authority and Organisation relevance score
            auth_score = 0.0
            if c.authority and c.authority in routed_authorities:
                auth_score += 0.5
            if c.organisation_id and c.organisation_id in routed_organisations:
                auth_score += 0.5
            elif c.authority == "SEBI":  # Apex regulator always carries institutional relevance
                auth_score = max(auth_score, 0.4)

            c.authority_score = auth_score

            # Metadata score combines authority score with process/domain alignment
            meta_score = auth_score
            if query.disputed_action and c.process and c.process.lower() in query.disputed_action.lower():
                meta_score = min(1.0, meta_score + 0.3)
            c.metadata_score = meta_score

            # 2. Combined hybrid score
            c.hybrid_score = (
                self.config.w_lexical * c.lexical_score
                + self.config.w_semantic * c.semantic_score
                + self.config.w_citation * c.citation_score
                + self.config.w_metadata * c.metadata_score
            )

            # 3. Evaluate temporal applicability
            scope = TemporalScope(
                publication_date=c.effective_date,
                effective_date=c.effective_date,
                termination_date=c.termination_date,
                superseded_status=SupersededStatus.SUPERSEDED if c.temporal_status == TemporalResolutionState.SUPERSEDED else SupersededStatus.CURRENT,
            )

            if eval_date is not None:
                t_state = self.temporal_engine.evaluate_applicability(scope, eval_date)
                c.temporal_status = t_state
                if t_state == TemporalResolutionState.APPLICABLE:
                    c.applicability_status = "APPLICABLE"
                elif t_state in {TemporalResolutionState.EXPIRED_OR_TERMINATED, TemporalResolutionState.NOT_YET_EFFECTIVE, TemporalResolutionState.SUPERSEDED}:
                    c.applicability_status = "NOT_APPLICABLE"
                else:
                    c.applicability_status = "TEMPORALITY_UNRESOLVED"
            else:
                c.temporal_status = TemporalResolutionState.TEMPORALITY_UNRESOLVED
                c.applicability_status = "TEMPORALITY_UNRESOLVED"

        return candidates
