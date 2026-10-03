"""Retrieval Evaluation Engine and Benchmark Runner for SANGYAN.

Epistemic foundation:
- Evaluates retrieval against real gold benchmark cases.
- Computes standard information retrieval metrics: Recall@5, Recall@10, Recall@20, Precision@5, Precision@10, MRR.
- Evaluates domain-specific correctness: Authority correctness, Organisation correctness, Temporal correctness, Citation correctness.
- Produces rigorous failure classification for misses.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Sequence
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ai.app.evaluation.benchmark_cases import GOLD_BENCHMARK_CASES, GoldBenchmarkCase
from ai.app.retrieval.contracts import RetrievalResponse
from ai.app.retrieval.retriever import ProvisionRetriever

logger = logging.getLogger("sangyan.evaluation.retrieval")


class BenchmarkCaseEvaluation(BaseModel):
    """Evaluation result for an individual benchmark case."""
    case_id: str
    description: str
    expected_provision_ids: list[str]
    retrieved_provision_ids: list[str] = Field(default_factory=list)
    top_5_ids: list[str] = Field(default_factory=list)
    top_10_ids: list[str] = Field(default_factory=list)
    top_20_ids: list[str] = Field(default_factory=list)

    # Retrieval metrics
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    recall_at_20: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    reciprocal_rank: float = 0.0

    # Domain correctness
    authority_correct: bool = True
    organisation_correct: bool = True
    temporal_correct: bool = True
    citation_correct: bool = True

    failure_reasons: list[str] = Field(default_factory=list)
    failure_classification: str | None = None
    retrieval_methods: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class BenchmarkSummary(BaseModel):
    """Aggregated retrieval benchmark metrics."""
    total_cases: int
    mean_recall_at_5: float
    mean_recall_at_10: float
    mean_recall_at_20: float
    mean_precision_at_5: float
    mean_precision_at_10: float
    mean_reciprocal_rank: float
    authority_correctness: float
    organisation_correctness: float
    temporal_correctness: float
    citation_correctness: float
    total_failures: int
    mean_latency_ms: float
    cases: list[BenchmarkCaseEvaluation] = Field(default_factory=list)


class RetrievalEvaluator:
    """Executes gold benchmark evaluation over a ProvisionRetriever."""

    def __init__(self, retriever: ProvisionRetriever) -> None:
        self.retriever = retriever

    async def evaluate_case(
        self,
        case: GoldBenchmarkCase,
        session: AsyncSession | None = None,
    ) -> BenchmarkCaseEvaluation:
        """Run single benchmark case and compute IR and domain metrics."""
        start = time.perf_counter()
        resp: RetrievalResponse = await self.retriever.retrieve(query=case.query, session=session)
        latency = (time.perf_counter() - start) * 1000

        retrieved_ids = [r.provision_id for r in resp.results]
        top_5 = retrieved_ids[:5]
        top_10 = retrieved_ids[:10]
        top_20 = retrieved_ids[:20]

        expected_set = set(case.expected_provision_ids)
        if not expected_set:
            recall_5 = recall_10 = recall_20 = 1.0
            p_5 = p_10 = 1.0
            rr = 1.0
        else:
            hits_5 = len(expected_set.intersection(set(top_5)))
            hits_10 = len(expected_set.intersection(set(top_10)))
            hits_20 = len(expected_set.intersection(set(top_20)))

            recall_5 = hits_5 / len(expected_set)
            recall_10 = hits_10 / len(expected_set)
            recall_20 = hits_20 / len(expected_set)

            p_5 = hits_5 / 5.0
            p_10 = hits_10 / 10.0

            rr = 0.0
            for rank, pid in enumerate(retrieved_ids, start=1):
                if pid in expected_set:
                    rr = 1.0 / rank
                    break

        # Authority Correctness
        auth_correct = True
        if case.expected_authorities:
            retrieved_auths = {r.authority for r in resp.results if r.authority}
            # Check overlap with expected authorities or routed authorities
            auth_correct = bool(set(case.expected_authorities).intersection(set(resp.routed_authorities).union(retrieved_auths)))

        # Organisation Correctness
        org_correct = True
        if case.expected_organisations:
            retrieved_orgs = {r.organisation_id for r in resp.results if r.organisation_id}
            org_correct = bool(set(case.expected_organisations).intersection(set(resp.routed_organisations).union(retrieved_orgs)))

        # Temporal Correctness
        temp_correct = True
        if case.query.incident_date:
            # If incident date provided, at least one result must have evaluated applicability
            temp_correct = any(r.applicability_status in {"APPLICABLE", "NOT_APPLICABLE"} for r in resp.results) if resp.results else False

        # Citation Correctness
        cit_correct = True
        if case.query.target_citations:
            cit_correct = any("exact_citation" in r.retrieval_methods for r in resp.results)

        # Failure Classification
        failure_class = None
        if recall_20 < 0.5:
            if not resp.results:
                failure_class = "NO_CANDIDATES_FOUND"
            elif not auth_correct:
                failure_class = "AUTHORITY_ROUTING_MISS"
            elif case.query.target_citations and not cit_correct:
                failure_class = "CITATION_MISS"
            elif not any(r.lexical_score and r.lexical_score > 0 for r in resp.results):
                failure_class = "LEXICAL_MISS"
            else:
                failure_class = "SEMANTIC_MISS"

        all_methods = list({m for r in resp.results for m in r.retrieval_methods})

        return BenchmarkCaseEvaluation(
            case_id=case.case_id,
            description=case.description,
            expected_provision_ids=case.expected_provision_ids,
            retrieved_provision_ids=retrieved_ids,
            top_5_ids=top_5,
            top_10_ids=top_10,
            top_20_ids=top_20,
            recall_at_5=round(recall_5, 4),
            recall_at_10=round(recall_10, 4),
            recall_at_20=round(recall_20, 4),
            precision_at_5=round(p_5, 4),
            precision_at_10=round(p_10, 4),
            reciprocal_rank=round(rr, 4),
            authority_correct=auth_correct,
            organisation_correct=org_correct,
            temporal_correct=temp_correct,
            citation_correct=cit_correct,
            failure_reasons=[r.value for r in resp.failure_reasons],
            failure_classification=failure_class,
            retrieval_methods=all_methods,
            latency_ms=round(latency, 2),
        )

    async def evaluate_all(
        self,
        cases: Sequence[GoldBenchmarkCase] | None = None,
        session: AsyncSession | None = None,
    ) -> BenchmarkSummary:
        """Run all gold benchmark cases and calculate aggregate statistics."""
        target_cases = cases or GOLD_BENCHMARK_CASES
        evaluations: list[BenchmarkCaseEvaluation] = []

        for case in target_cases:
            res = await self.evaluate_case(case, session=session)
            evaluations.append(res)

        n = len(evaluations)
        if n == 0:
            return BenchmarkSummary(
                total_cases=0,
                mean_recall_at_5=0.0,
                mean_recall_at_10=0.0,
                mean_recall_at_20=0.0,
                mean_precision_at_5=0.0,
                mean_precision_at_10=0.0,
                mean_reciprocal_rank=0.0,
                authority_correctness=0.0,
                organisation_correctness=0.0,
                temporal_correctness=0.0,
                citation_correctness=0.0,
                total_failures=0,
                mean_latency_ms=0.0,
                cases=[],
            )

        summary = BenchmarkSummary(
            total_cases=n,
            mean_recall_at_5=round(sum(e.recall_at_5 for e in evaluations) / n, 4),
            mean_recall_at_10=round(sum(e.recall_at_10 for e in evaluations) / n, 4),
            mean_recall_at_20=round(sum(e.recall_at_20 for e in evaluations) / n, 4),
            mean_precision_at_5=round(sum(e.precision_at_5 for e in evaluations) / n, 4),
            mean_precision_at_10=round(sum(e.precision_at_10 for e in evaluations) / n, 4),
            mean_reciprocal_rank=round(sum(e.reciprocal_rank for e in evaluations) / n, 4),
            authority_correctness=round(sum(1.0 for e in evaluations if e.authority_correct) / n, 4),
            organisation_correctness=round(sum(1.0 for e in evaluations if e.organisation_correct) / n, 4),
            temporal_correctness=round(sum(1.0 for e in evaluations if e.temporal_correct) / n, 4),
            citation_correctness=round(sum(1.0 for e in evaluations if e.citation_correct) / n, 4),
            total_failures=sum(1 for e in evaluations if e.failure_classification is not None),
            mean_latency_ms=round(sum(e.latency_ms for e in evaluations) / n, 2),
            cases=evaluations,
        )

        return summary
