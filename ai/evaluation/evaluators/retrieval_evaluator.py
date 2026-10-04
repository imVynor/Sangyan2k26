"""Epistemic Provision Retrieval Evaluator for SANGYAN (Phase 7A).

Epistemic foundation:
- Computes IR metrics: Recall@1, Recall@5, Recall@10, Recall@20, MRR, nDCG@10.
- Separately evaluates 'required-provision recall' to prevent Recall@10 from masking
  omissions of the critical governing rule.
- Classifies retrieval misses: CORPUS_GAP, TEMPORAL_MISS, AUTHORITY_MISS, etc.
"""

import math
import logging
from typing import Any, Sequence

from ai.evaluation.corpus.models import (
    EvaluationCase,
    ExpectedProvision,
    StageEvaluationResult,
)
from ai.evaluation.corpus.taxonomy import RetrievalFailureClass, RetrievalRelevance

logger = logging.getLogger("sangyan.evaluation.retrieval")


class ProvisionRetrievalEvaluator:
    """Evaluates provision retrieval performance, ranking, and failure taxonomy."""

    def evaluate(
        self,
        case: EvaluationCase,
        retrieved_provision_ids: Sequence[str],
        retrieved_details: Sequence[dict[str, Any]] | None = None,
    ) -> StageEvaluationResult:
        if not case.expected_provisions and not case.is_blocked_by_corpus_gap:
            return StageEvaluationResult(
                stage_name="PROVISION_RETRIEVAL",
                passed=True,
                score=1.0,
                details={"skipped": True, "reason": "No expected provisions specified"},
            )

        # Handle explicit corpus gap case (Section 24 & 36)
        if case.is_blocked_by_corpus_gap:
            return StageEvaluationResult(
                stage_name="PROVISION_RETRIEVAL",
                passed=True,
                score=1.0,
                details={
                    "is_blocked_by_corpus_gap": True,
                    "corpus_gap_reason": case.corpus_gap_reason,
                    "retrieved_count": len(retrieved_provision_ids),
                },
                discrepancies=[],
                failure_class=RetrievalFailureClass.CORPUS_GAP.value,
            )

        gold_required = [
            p.provision_id for p in case.expected_provisions
            if p.relevance == RetrievalRelevance.REQUIRED
        ]
        gold_all = [p.provision_id for p in case.expected_provisions] + list(case.acceptable_provisions)

        retrieved_list = list(retrieved_provision_ids)
        top_1 = set(retrieved_list[:1])
        top_5 = set(retrieved_list[:5])
        top_10 = set(retrieved_list[:10])
        top_20 = set(retrieved_list[:20])

        gold_set = set(gold_all)
        required_set = set(gold_required)

        # 1. Recall metrics
        hits_at_1 = len(top_1.intersection(gold_set))
        hits_at_5 = len(top_5.intersection(gold_set))
        hits_at_10 = len(top_10.intersection(gold_set))
        hits_at_20 = len(top_20.intersection(gold_set))

        denom = len(gold_set) if gold_set else 1
        recall_at_1 = min(1.0, hits_at_1 / denom)
        recall_at_5 = min(1.0, hits_at_5 / denom)
        recall_at_10 = min(1.0, hits_at_10 / denom)
        recall_at_20 = min(1.0, hits_at_20 / denom)

        # Required-provision recall
        req_denom = len(required_set) if required_set else 1
        req_hits_at_10 = len(top_10.intersection(required_set))
        required_recall = min(1.0, req_hits_at_10 / req_denom)

        # 2. Reciprocal Rank (MRR)
        reciprocal_rank = 0.0
        first_gold_rank = None
        for rank_idx, pid in enumerate(retrieved_list, start=1):
            if pid in gold_set:
                reciprocal_rank = 1.0 / rank_idx
                first_gold_rank = rank_idx
                break

        # 3. nDCG@10
        dcg = 0.0
        for i, pid in enumerate(retrieved_list[:10]):
            rel = 2.0 if pid in required_set else (1.0 if pid in gold_set else 0.0)
            if rel > 0:
                dcg += rel / math.log2(i + 2)

        idcg = 0.0
        ideal_rels = sorted(
            [2.0 if pid in required_set else 1.0 for pid in gold_set],
            reverse=True,
        )[:10]
        for i, rel in enumerate(ideal_rels):
            idcg += rel / math.log2(i + 2)

        ndcg_at_10 = (dcg / idcg) if idcg > 0 else 0.0

        # Discrepancies and failure classification
        discrepancies: list[str] = []
        failure_class = None

        if required_recall < 1.0:
            missing_req = required_set - top_10
            discrepancies.append(
                f"Missing critical required provisions in top-10: {list(missing_req)}"
            )

            # Classify failure
            if any(pid in top_20 for pid in missing_req):
                failure_class = RetrievalFailureClass.RERANKING_MISS.value
            elif case.category.value == "temporal":
                failure_class = RetrievalFailureClass.TEMPORAL_MISS.value
            elif case.category.value == "cross_document":
                failure_class = RetrievalFailureClass.CROSS_DOCUMENT_MISS.value
            else:
                failure_class = RetrievalFailureClass.EMBEDDING_MISS.value

        passed = required_recall >= 1.0

        return StageEvaluationResult(
            stage_name="PROVISION_RETRIEVAL",
            passed=passed,
            score=required_recall,
            details={
                "recall_at_1": recall_at_1,
                "recall_at_5": recall_at_5,
                "recall_at_10": recall_at_10,
                "recall_at_20": recall_at_20,
                "required_recall": required_recall,
                "reciprocal_rank": reciprocal_rank,
                "first_gold_rank": first_gold_rank,
                "ndcg_at_10": ndcg_at_10,
                "top_10_retrieved": retrieved_list[:10],
                "gold_required": gold_required,
            },
            discrepancies=discrepancies,
            failure_class=failure_class,
        )
