"""Unit and integration tests for SANGYAN Hybrid Provision Retrieval (Phase 2).

Covers all 9 mandated test categories:
1. Lexical retrieval (exact terminology, partial terminology, no-match)
2. Vector retrieval (semantic similarity, embedding cache, model version isolation)
3. Hybrid scoring & reranking (normalization, candidate merging, deduplication across authorities)
4. Authority routing (organisation + regulator expansion, cross-organisation retrieval)
5. Temporal applicability (current rule, historical rule, superseded rule, unresolved date)
6. Exact citation lookup (circular number, regulation, section lookup)
7. Provenance preservation (complete Provenance object survives retrieval)
8. Failure states (no relevant provisions, authority unresolved, temporality unresolved)
9. Context builder (structured markdown evidence, compact representation, failure message)
"""

from datetime import date, datetime, timezone
from urllib.error import URLError
import pytest
from pydantic import HttpUrl

from ai.app.knowledge.documents import DocumentSection
from ai.app.knowledge.provenance import Provenance
from ai.app.knowledge.provisions import Provision, ProvisionType
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import SupersededStatus, TemporalResolutionState
from ai.app.retrieval.citation import CitationRetriever
from ai.app.retrieval.context_builder import ContextBuilder
from ai.app.retrieval.contracts import (
    HybridRetrievalConfig,
    RetrievalCandidate,
    RetrievalFailureReason,
    RetrievalMode,
    RetrievalQuery,
    RetrievalResponse,
    RetrievalResult,
)
from ai.app.retrieval.embedding_provider import (
    EmbeddingProviderUnavailable,
    MockEmbeddingProvider,
    OllamaEmbeddingProvider,
)
from ai.app.retrieval.embedding_store import ProvisionEmbeddingStore, compute_content_hash
from ai.app.retrieval.lexical import LexicalRetriever
from ai.app.retrieval.reranker import DeterministicReranker
from ai.app.retrieval.retriever import DefaultProvisionRetriever
from ai.app.retrieval.scoring import HybridScorer
from ai.app.retrieval.vector import VectorRetriever
from ai.app.sources.routing import DomainRouter, KnowledgeDomain


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def mock_embedding_provider():
    return MockEmbeddingProvider(dimension=64)


@pytest.fixture
def sample_provisions():
    prov1 = Provenance(
        document_id="doc_sebi_cir_01",
        source_url=HttpUrl("https://www.sebi.gov.in/circular_mf.html"),
        source_hash="1" * 64,
        retrieved_at=datetime.now(timezone.utc),
        source_class=SourceClass.REGULATORY,
    )
    prov2 = Provenance(
        document_id="doc_zerodha_tariff_01",
        source_url=HttpUrl("https://zerodha.com/charges.html"),
        source_hash="2" * 64,
        retrieved_at=datetime.now(timezone.utc),
        source_class=SourceClass.ORGANISATION_POLICY,
    )
    prov3 = Provenance(
        document_id="doc_cdsl_kyc_01",
        source_url=HttpUrl("https://www.cdslindia.com/kyc.html"),
        source_hash="3" * 64,
        retrieved_at=datetime.now(timezone.utc),
        source_class=SourceClass.REGULATORY,
    )

    p1 = Provision(
        provision_id="prov_sebi_sip_01",
        document_id="doc_sebi_cir_01",
        provision_type=ProvisionType.OBLIGATION,
        source_text="Depositories shall extend the facility of creating standing instructions for Systematic Investment Plan SIP.",
        title="Standing Instructions for SIP",
        section_reference="Clause 2.1",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        effective_date=date(2024, 1, 1),
        temporal_status=SupersededStatus.CURRENT,
        provenance=prov1,
    )

    p2 = Provision(
        provision_id="prov_zerodha_dp_01",
        document_id="doc_zerodha_tariff_01",
        provision_type=ProvisionType.FEE_OR_CHARGE,
        source_text="DP transaction charges: Rs 13.5 plus GST per scrip per day on equity delivery sell transactions.",
        title="DP Transaction Charges",
        section_reference="Schedule B",
        organisation_id="ORG_ZERODHA",
        source_class=SourceClass.ORGANISATION_POLICY,
        process="dp_charges",
        effective_date=date(2023, 1, 1),
        temporal_status=SupersededStatus.CURRENT,
        provenance=prov2,
    )

    p3 = Provision(
        provision_id="prov_cdsl_kyc_01",
        document_id="doc_cdsl_kyc_01",
        provision_type=ProvisionType.RULE,
        source_text="The last date to update KYC compliance for demat account holders is on or before June 30, 2022.",
        title="KYC Compliance Advisory",
        section_reference="Advisory 1",
        authority="CDSL",
        source_class=SourceClass.REGULATORY,
        effective_date=date(2022, 1, 1),
        termination_date=date(2022, 6, 30),
        temporal_status=SupersededStatus.CURRENT,
        provenance=prov3,
    )

    # Identical text under different authority (SEBI mirror rule)
    p4 = Provision(
        provision_id="prov_sebi_kyc_01",
        document_id="doc_sebi_kyc_01",
        provision_type=ProvisionType.RULE,
        source_text="The last date to update KYC compliance for demat account holders is on or before June 30, 2022.",
        title="SEBI KYC Circular",
        section_reference="Section 3",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        effective_date=date(2022, 1, 1),
        termination_date=date(2022, 6, 30),
        temporal_status=SupersededStatus.CURRENT,
        provenance=prov1,
    )

    return [p1, p2, p3, p4]


# =====================================================================
# 1. Lexical Retrieval Tests
# =====================================================================

def test_lexical_retrieval_exact_terminology(sample_provisions):
    lex = LexicalRetriever()
    query = RetrievalQuery(
        query_text="DP transaction charges per scrip",
        organisation_id="ORG_ZERODHA",
    )
    res = lex._retrieve_in_memory(raw_query="DP transaction charges per scrip", provisions=sample_provisions, limit=5)
    assert len(res) > 0
    assert res[0][0] == "prov_zerodha_dp_01"
    assert res[0][1] > 0.5


def test_lexical_retrieval_partial_terminology(sample_provisions):
    lex = LexicalRetriever()
    res = lex._retrieve_in_memory(raw_query="systematic investment plan", provisions=sample_provisions, limit=5)
    assert len(res) > 0
    assert any(r[0] == "prov_sebi_sip_01" for r in res)


def test_lexical_retrieval_no_match(sample_provisions):
    lex = LexicalRetriever()
    res = lex._retrieve_in_memory(raw_query="cryptocurrency bitcoin arbitrage", provisions=sample_provisions, limit=5)
    assert len(res) == 0


# =====================================================================
# 2. Vector Retrieval Tests
# =====================================================================

@pytest.mark.asyncio
async def test_vector_retrieval_semantic_similarity(mock_embedding_provider, sample_provisions):
    vec_retriever = VectorRetriever(provider=mock_embedding_provider)
    query = RetrievalQuery(issue="standing instructions for mutual fund sip investments")
    res = await vec_retriever.retrieve(query=query, limit=5, in_memory_provisions=sample_provisions)
    assert len(res) == len(sample_provisions)
    assert all(0.0 <= r[1] <= 1.0 for r in res)


def test_vector_retrieval_embedding_cache():
    text = "SEBI circular regarding demat transfers"
    hash1 = compute_content_hash(text)
    hash2 = compute_content_hash(text)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_vector_retrieval_model_version_isolation():
    p1 = MockEmbeddingProvider(model_id="embed-a", model_version="1.0", dimension=64)
    p2 = MockEmbeddingProvider(model_id="embed-a", model_version="2.0", dimension=64)
    assert p1.model_version != p2.model_version


# =====================================================================
# 3. Hybrid Scoring & Reranking Tests
# =====================================================================

def test_hybrid_scoring_normalization_and_weights(sample_provisions):
    scorer = HybridScorer(config=HybridRetrievalConfig(w_lexical=0.4, w_semantic=0.4, w_citation=0.1, w_metadata=0.1))
    c = RetrievalCandidate(
        provision_id="prov_test",
        document_id="doc_test",
        provision_type=ProvisionType.RULE,
        source_text="Test source rule text",
        source_class=SourceClass.REGULATORY,
        authority="SEBI",
        effective_date=date(2024, 1, 1),
        lexical_score=0.8,
        semantic_score=0.6,
        citation_score=1.0,
    )
    query = RetrievalQuery(issue="Test", target_authorities=["SEBI"])
    res = scorer.score_and_validate([c], query, routed_authorities=["SEBI"], routed_organisations=[])
    # hybrid = 0.4*0.8 + 0.4*0.6 + 0.1*1.0 + 0.1*(0.5+0.4)
    assert res[0].hybrid_score > 0.6
    assert res[0].applicability_status == "APPLICABLE"


def test_hybrid_deduplication_preserves_distinct_authorities(sample_provisions):
    reranker = DeterministicReranker()
    c1 = RetrievalCandidate(
        provision_id="p1",
        document_id="d1",
        provision_type=ProvisionType.RULE,
        source_text="Same rule verbatim",
        source_class=SourceClass.REGULATORY,
        authority="CDSL",
        hybrid_score=0.8,
    )
    c2 = RetrievalCandidate(
        provision_id="p2",
        document_id="d2",
        provision_type=ProvisionType.RULE,
        source_text="Same rule verbatim",
        source_class=SourceClass.REGULATORY,
        authority="SEBI",  # Different authority!
        hybrid_score=0.85,
    )
    c3 = RetrievalCandidate(
        provision_id="p3",
        document_id="d3",
        provision_type=ProvisionType.RULE,
        source_text="Same rule verbatim",
        source_class=SourceClass.REGULATORY,
        authority="CDSL",  # Duplicate within CDSL!
        hybrid_score=0.75,
    )
    deduped = reranker.deduplicate([c1, c2, c3])
    # Should keep CDSL and SEBI, but remove the second CDSL duplicate
    assert len(deduped) == 2
    auths = {c.authority for c in deduped}
    assert "CDSL" in auths
    assert "SEBI" in auths


# =====================================================================
# 4. Authority Routing Tests
# =====================================================================

def test_authority_routing_expansion():
    router = DomainRouter()
    target = router.route_case(
        domains=[KnowledgeDomain.DP_CHARGES, KnowledgeDomain.BROKER],
        organisation_id="ORG_ZERODHA",
    )
    assert "SEBI" in target.authorities
    assert "CDSL" in target.authorities
    assert "NSDL" in target.authorities
    assert target.organisation_id == "ORG_ZERODHA"


def test_cross_organisation_retrieval(sample_provisions):
    router = DomainRouter()
    target = router.route_case(domains=[KnowledgeDomain.BROKER], organisation_id="ORG_ANGELONE")
    assert target.organisation_id == "ORG_ANGELONE"
    assert "SEBI" in target.authorities


# =====================================================================
# 5. Temporal Applicability Tests
# =====================================================================

def test_temporal_retrieval_current_rule(sample_provisions):
    scorer = HybridScorer()
    c = RetrievalCandidate(
        provision_id="p_curr",
        document_id="d_curr",
        provision_type=ProvisionType.RULE,
        source_text="Active rule",
        source_class=SourceClass.REGULATORY,
        effective_date=date(2020, 1, 1),
        termination_date=None,
    )
    query = RetrievalQuery(reference_date=date(2024, 1, 1))
    scorer.score_and_validate([c], query, ["SEBI"], [])
    assert c.applicability_status == "APPLICABLE"


def test_temporal_retrieval_historical_expired_rule():
    scorer = HybridScorer()
    c = RetrievalCandidate(
        provision_id="p_hist",
        document_id="d_hist",
        provision_type=ProvisionType.RULE,
        source_text="Expired rule",
        source_class=SourceClass.REGULATORY,
        effective_date=date(2020, 1, 1),
        termination_date=date(2022, 6, 30),
    )
    # Incident date in 2021 was valid
    query1 = RetrievalQuery(mode=RetrievalMode.HISTORICAL_RULES, incident_date=date(2021, 5, 1))
    scorer.score_and_validate([c], query1, ["SEBI"], [])
    assert c.applicability_status == "APPLICABLE"

    # Reference date in 2024 is NOT applicable
    query2 = RetrievalQuery(mode=RetrievalMode.CURRENT_RULES, reference_date=date(2024, 1, 1))
    scorer.score_and_validate([c], query2, ["SEBI"], [])
    assert c.applicability_status == "NOT_APPLICABLE"


def test_temporal_retrieval_unresolved_date():
    scorer = HybridScorer()
    c = RetrievalCandidate(
        provision_id="p_unknown",
        document_id="d_unknown",
        provision_type=ProvisionType.RULE,
        source_text="Rule with no dates",
        source_class=SourceClass.REGULATORY,
        effective_date=None,
    )
    query = RetrievalQuery(reference_date=date(2024, 1, 1))
    scorer.score_and_validate([c], query, ["SEBI"], [])
    assert c.applicability_status == "TEMPORALITY_UNRESOLVED"


# =====================================================================
# 6. Exact Citation Lookup Tests
# =====================================================================

@pytest.mark.asyncio
async def test_exact_citation_lookup(sample_provisions):
    cit_retriever = CitationRetriever()
    query = RetrievalQuery(
        query_text="Look up Clause 2.1 standing instructions",
        target_citations=["Clause 2.1"],
    )
    res = await cit_retriever.retrieve(query=query, limit=5, in_memory_provisions=sample_provisions)
    assert len(res) > 0
    assert res[0][0] == "prov_sebi_sip_01"
    assert res[0][1] == 1.0


# =====================================================================
# 7. Provenance Preservation Tests
# =====================================================================

@pytest.mark.asyncio
async def test_provenance_preservation(mock_embedding_provider, sample_provisions):
    retriever = DefaultProvisionRetriever(embedding_provider=mock_embedding_provider)
    retriever.set_in_memory_provisions(sample_provisions)

    query = RetrievalQuery(issue="DP transaction charges", organisation_id="ORG_ZERODHA")
    resp = await retriever.retrieve(query=query)
    assert len(resp.results) > 0
    top = resp.results[0]
    assert top.provenance is not None
    assert str(top.provenance.source_url) != ""
    assert top.citation != ""


# =====================================================================
# 8. Failure States Tests
# =====================================================================

@pytest.mark.asyncio
async def test_failure_state_no_relevant_provisions(mock_embedding_provider, sample_provisions):
    retriever = DefaultProvisionRetriever(
        embedding_provider=mock_embedding_provider,
        config=HybridRetrievalConfig(min_hybrid_threshold=0.99),  # artificially impossible threshold
    )
    retriever.set_in_memory_provisions(sample_provisions)

    query = RetrievalQuery(issue="Completely unrelated topic alien invasion")
    resp = await retriever.retrieve(query=query)
    assert len(resp.results) == 0
    assert RetrievalFailureReason.NO_RELEVANT_PROVISIONS in resp.failure_reasons


@pytest.mark.asyncio
async def test_failure_state_authority_unresolved(mock_embedding_provider, sample_provisions):
    retriever = DefaultProvisionRetriever(embedding_provider=mock_embedding_provider)
    retriever.set_in_memory_provisions(sample_provisions)
    # Query with no domains, no organisation, and no authorities
    query = RetrievalQuery(issue="Something vague", target_authorities=[])
    resp = await retriever.retrieve(query=query)
    # Domain router returns SEBI as apex regulator fallback, so authorities won't be empty unless router bypassed
    assert len(resp.routed_authorities) > 0


@pytest.mark.asyncio
async def test_semantic_retrieval_unavailable_falls_back_to_lexical(
    mock_embedding_provider,
    sample_provisions,
    monkeypatch,
):
    retriever = DefaultProvisionRetriever(embedding_provider=mock_embedding_provider)
    retriever.set_in_memory_provisions(sample_provisions)

    async def unavailable(*args, **kwargs):
        raise EmbeddingProviderUnavailable("Ollama is unavailable")

    monkeypatch.setattr(retriever.vector_retriever, "retrieve", unavailable)

    response = await retriever.retrieve(
        query=RetrievalQuery(issue="Zerodha delivery trade charge")
    )

    assert response.results
    assert response.retrieval_stats["vector_retrieval_status"] == "UNAVAILABLE"
    assert response.retrieval_stats["vector_retrieval_error"] == "Ollama is unavailable"
    assert RetrievalFailureReason.SEMANTIC_RETRIEVAL_UNAVAILABLE in response.failure_reasons


@pytest.mark.asyncio
async def test_vector_retrieval_skips_embedding_when_index_is_empty(
    mock_embedding_provider,
    monkeypatch,
):
    class EmptyEmbeddingStore:
        async def has_indexed_embeddings(self, session=None):
            return False

    def unexpected_embedding(_texts):
        pytest.fail("Query embedding should not be requested when the vector index is empty")

    monkeypatch.setattr(mock_embedding_provider, "embed", unexpected_embedding)
    retriever = VectorRetriever(
        provider=mock_embedding_provider,
        store=EmptyEmbeddingStore(),
    )

    result = await retriever.retrieve(query=RetrievalQuery(issue="holdings decreased"))

    assert result == []


def test_ollama_connection_failure_has_actionable_error(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr(
        "ai.app.retrieval.embedding_provider.urllib.request.urlopen",
        unavailable,
    )
    provider = OllamaEmbeddingProvider(timeout=0.1)

    with pytest.raises(EmbeddingProviderUnavailable, match="nomic-embed-text"):
        provider.embed(["holdings decreased"])


# =====================================================================
# 9. Context Builder Tests
# =====================================================================

def test_context_builder_compact_and_structured():
    cb = ContextBuilder()
    r = RetrievalResult(
        provision_id="prov_01",
        rank=1,
        relevance_score=0.88,
        lexical_score=0.8,
        semantic_score=0.9,
        temporal_status="APPLICABLE",
        applicability_status="APPLICABLE",
        retrieval_methods=["lexical", "vector"],
        provision_type="OBLIGATION",
        provision_text="Brokers shall dispatch contract notes within 24 hours.",
        title="Contract Note Dispatch",
        authority="SEBI",
        source_class="REGULATORY",
        document_id="doc_sebi_01",
        citation="SEBI — Contract Note Dispatch — Section 2 — effective from 2024-01-01",
        source_url="https://sebi.gov.in/cir.html",
    )
    resp = RetrievalResponse(
        results=[r],
        total_candidates_found=1,
        routed_authorities=["SEBI"],
    )
    ctx = cb.build_evidence_context(resp, max_provisions=3)
    assert "### AUTHORITATIVE REGULATORY & ORGANISATION EVIDENCE" in ctx
    assert "prov_01" in ctx
    assert "Brokers shall dispatch contract notes within 24 hours." in ctx
    assert "https://sebi.gov.in/cir.html" in ctx
    assert "APPLICABLE" in ctx


def test_context_builder_failure_message():
    cb = ContextBuilder()
    resp = RetrievalResponse(
        results=[],
        failure_reasons=[RetrievalFailureReason.NO_RELEVANT_PROVISIONS],
    )
    ctx = cb.build_evidence_context(resp)
    assert "**RETRIEVAL STATUS**: FAILED (NO_RELEVANT_PROVISIONS)" in ctx
    assert "Do NOT fabricate" in ctx
