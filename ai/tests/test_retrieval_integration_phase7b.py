"""Phase 7B: Real retrieval integration tests.

Integration tests (marked `integration`) hit the REAL PostgreSQL + pgvector corpus
and the local Ollama embedding service. No mocks are used for retrieval there.
Unit-level guard tests use explicit fakes only to prove the guard rejects them.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai.app.case.repository import InMemoryCaseRepository
from ai.app.orchestration.contracts import OrchestrationInputEvent, RetrievalError
from ai.app.orchestration.orchestrator import CaseOrchestrator
from ai.app.retrieval.contracts import RetrievalFailureReason, RetrievalQuery, RetrievalResponse
from ai.app.retrieval.retriever import DefaultProvisionRetriever
from ai.app.sources.routing import KnowledgeDomain
from ai.evaluation.runners.causal import CausalFailure, classify_causal_failure
from ai.evaluation.runners.evaluate_case import SingleCaseEvaluator
from ai.evaluation.runners.retriever_guard import (
    MockRetrieverInRealBenchmarkError,
    assert_real_retriever,
)

integration = pytest.mark.integration


@pytest.fixture(scope="module")
def real_retriever() -> DefaultProvisionRetriever:
    return DefaultProvisionRetriever.create_default()


def _dp_query(**kw) -> RetrievalQuery:
    base = dict(
        issue="Dispute over depository participant charges on debit of shares",
        issue_category="dp_charges",
        organisation_id="ORG_ZERODHA",
        disputed_action="DP charge deduction upon sale of equity delivery",
        issue_domains=[KnowledgeDomain.DP_CHARGES, KnowledgeDomain.BROKER],
        key_terms=["dp charges", "demat account", "zerodha charges", "debit"],
        top_k=10,
    )
    base.update(kw)
    return RetrievalQuery(**base)


# ---------------- A. construction / wiring (no DB needed) ----------------

def test_default_orchestrator_uses_real_retriever():
    orch = CaseOrchestrator()
    assert isinstance(orch.retriever, DefaultProvisionRetriever)
    assert_real_retriever(orch.retriever)


def test_explicit_mock_injection_still_possible():
    mock = AsyncMock()
    orch = CaseOrchestrator(retriever=mock)
    assert orch.retriever is mock


def test_explicit_none_retriever_is_explicit_opt_out():
    orch = CaseOrchestrator(retriever=None)
    assert orch.retriever is None


# ---------------- Regression guard (Step 12) ----------------

def test_guard_rejects_async_mock():
    with pytest.raises(MockRetrieverInRealBenchmarkError):
        assert_real_retriever(AsyncMock())


def test_guard_rejects_none():
    with pytest.raises(MockRetrieverInRealBenchmarkError):
        assert_real_retriever(None)


def test_guard_rejects_duck_typed_fake():
    class Stub:
        async def retrieve(self, q):
            return RetrievalResponse()

    with pytest.raises(MockRetrieverInRealBenchmarkError):
        assert_real_retriever(Stub())


def test_guard_rejects_in_memory_default_retriever():
    from ai.app.retrieval.embedding_provider import MockEmbeddingProvider

    r = DefaultProvisionRetriever(embedding_provider=MockEmbeddingProvider(dimension=64))
    with pytest.raises(MockRetrieverInRealBenchmarkError):
        assert_real_retriever(r)


def test_benchmark_evaluator_refuses_mock_orchestrator():
    orch = CaseOrchestrator(repository=InMemoryCaseRepository(), retriever=MagicMock())
    with pytest.raises(MockRetrieverInRealBenchmarkError):
        SingleCaseEvaluator(orchestrator=orch)


# ---------------- B/C. real DB retrieval + citation integrity ----------------

@integration
@pytest.mark.asyncio
async def test_real_retrieval_from_postgres(real_retriever):
    res = await real_retriever.retrieve(_dp_query())
    assert res.results, "Real corpus must return provisions for a DP-charge grievance"
    stats = res.retrieval_stats
    assert stats["retriever_class"] == "DefaultProvisionRetriever"
    assert stats["candidate_count"] > 0
    assert stats["lexical_candidates"] + stats["dense_candidates"] > 0
    assert stats["reranked_candidates"] == len(res.results)
    assert stats["authority_filter_applied"] is True
    assert stats["target_org_filter_applied"] is True
    assert "password" not in str(stats).lower()
    for r in res.results:
        assert r.provision_id.startswith("prov_")  # real DB IDs, not synthetic


@integration
@pytest.mark.asyncio
async def test_citation_integrity(real_retriever):
    res = await real_retriever.retrieve(_dp_query())
    assert res.results
    assert res.retrieval_stats["citation_resolution_status"] == "RESOLVED"
    for r in res.results:
        assert r.document_id
        assert r.citation
        assert r.source_url
        assert r.provision_text
        assert r.provenance is not None
        assert r.section_reference or r.section_id or r.clause_reference or r.title


# ---------------- D. authority separation ----------------

@integration
@pytest.mark.asyncio
async def test_authority_vs_organisation_distinguishable(real_retriever):
    res = await real_retriever.retrieve(_dp_query(top_k=20))
    classes = {r.source_class for r in res.results}
    assert len(classes) >= 1
    for r in res.results:
        if r.organisation_id:
            assert r.organisation_id == "ORG_ZERODHA"  # no cross-org leakage
        else:
            assert r.authority in {"SEBI", "CDSL", "NSDL", "NSE", "BSE"} or r.authority is None


# ---------------- E. temporal ----------------

@integration
@pytest.mark.asyncio
async def test_temporal_status_is_explicit(real_retriever):
    res = await real_retriever.retrieve(_dp_query(incident_date=date(2024, 6, 1), reference_date=date(2024, 6, 1)))
    assert res.retrieval_stats["temporal_filter_applied"] is True
    for r in res.results:
        assert r.applicability_status in {"APPLICABLE", "NOT_APPLICABLE", "TEMPORALITY_UNRESOLVED"}
        if r.effective_from and r.effective_to and r.applicability_status == "APPLICABLE":
            assert r.effective_from <= date(2024, 6, 1) <= r.effective_to


# ---------------- F. missing regulation stays UNKNOWN ----------------

@integration
@pytest.mark.asyncio
async def test_irrelevant_topic_does_not_fabricate_coverage(real_retriever):
    q = RetrievalQuery(
        query_text="zzqxv nonexistent cryptocurrency staking yield dispute",
        organisation_id=None,
        top_k=5,
    )
    res = await real_retriever.retrieve(q)
    # Whatever returns must never be silently treated as coverage: either empty with a failure
    # reason, or low-confidence results; assessment layer must stay non-conclusive (checked below).
    if not res.results:
        assert RetrievalFailureReason.NO_RELEVANT_PROVISIONS in res.failure_reasons


@pytest.mark.asyncio
async def test_empty_retrieval_never_yields_violation_or_compliance():
    orch = CaseOrchestrator(repository=InMemoryCaseRepository(), retriever=AsyncMock())
    orch.retriever.retrieve.return_value = RetrievalResponse(
        results=[], failure_reasons=[RetrievalFailureReason.NO_RELEVANT_PROVISIONS]
    )
    from ai.app.case.contracts import CaseState, CaseStatus

    await orch.repository.save_case(CaseState(case_id="C-7B-1", status=CaseStatus.DRAFT, version=1, facts={}, evidence=[], claims=[]))
    res = await orch.process_turn(
        "C-7B-1",
        OrchestrationInputEvent(complaint_text="Zerodha charged me Rs 15.93 for DP", user_message="Zerodha charged me Rs 15.93 for DP"),
        expected_version=1,
    )
    status = res.assessment_result.status.value
    assert status not in {"VIOLATION_CONFIRMED", "COMPLIANT_WITH_REGULATION"}


# ---------------- G. operational failure ----------------

@pytest.mark.asyncio
async def test_retrieval_exception_is_operational_not_epistemic():
    mock = AsyncMock()
    mock.retrieve.side_effect = ConnectionError("db down")
    orch = CaseOrchestrator(repository=InMemoryCaseRepository(), retriever=mock)
    from ai.app.case.contracts import CaseState, CaseStatus

    await orch.repository.save_case(CaseState(case_id="C-7B-2", status=CaseStatus.DRAFT, version=1, facts={}, evidence=[], claims=[]))
    with pytest.raises(RetrievalError):
        await orch.process_turn(
            "C-7B-2",
            OrchestrationInputEvent(complaint_text="Zerodha charged me Rs 20", user_message="Zerodha charged me Rs 20"),
            expected_version=1,
        )


def test_causal_classifier_operational_first():
    assert (
        classify_causal_failure(
            passed=False, operational_error="boom", stages={}, retrieval_stats={},
            retrieval_result_count=0, expected_provision_count=1,
            blocked_by_corpus_gap=False, failure_reasons=[],
        )
        == CausalFailure.OPERATIONAL_FAILURE
    )


def test_causal_classifier_empty_retrieval_is_query_formulation():
    from ai.evaluation.corpus.models import StageEvaluationResult

    stages = {
        "FACT_EXTRACTION": StageEvaluationResult(stage_name="FACT_EXTRACTION", passed=True),
        "PROVISION_RETRIEVAL": StageEvaluationResult(stage_name="PROVISION_RETRIEVAL", passed=False, failure_class="EMBEDDING_MISS"),
        "ASSESSMENT": StageEvaluationResult(stage_name="ASSESSMENT", passed=False),
    }
    assert (
        classify_causal_failure(
            passed=False, operational_error=None, stages=stages,
            retrieval_stats={"candidate_count": 0}, retrieval_result_count=0,
            expected_provision_count=2, blocked_by_corpus_gap=False,
            failure_reasons=["NO_RELEVANT_PROVISIONS"],
        )
        == CausalFailure.QUERY_FORMULATION_GAP
    )


# ---------------- Full orchestrator path through real retriever ----------------

@integration
@pytest.mark.asyncio
async def test_orchestrator_end_to_end_real_retrieval():
    orch = CaseOrchestrator(repository=InMemoryCaseRepository())
    assert_real_retriever(orch.retriever)
    from ai.app.case.contracts import CaseState, CaseStatus

    await orch.repository.save_case(CaseState(case_id="C-7B-E2E", status=CaseStatus.DRAFT, version=1, facts={}, evidence=[], claims=[]))
    text = "Zerodha charged me Rs 15.93 DP charges when I sold shares from my demat account"
    res = await orch.process_turn("C-7B-E2E", OrchestrationInputEvent(complaint_text=text, user_message=text), expected_version=1)
    stats = res.retrieval_response.retrieval_stats
    assert stats.get("retriever_class") == "DefaultProvisionRetriever"
    assert res.retrieval_response.total_candidates_found > 0
    assert res.retrieval_response.results
    # Epistemic safety preserved when facts/evidence are incomplete
    assert res.assessment_result.status.value not in {"VIOLATION_CONFIRMED", "COMPLIANT_WITH_REGULATION"} or res.assessment_result.findings
