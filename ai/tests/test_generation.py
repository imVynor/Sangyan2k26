"""Unit tests for SANGYAN Auditable Response Generation Layer.

Covers:
1. Grounded citizen-facing explanation with verified citations
2. Rejection of unsupplied or hallucinated citations (INVALID_CITATION)
3. Rejection of unsupported claims during EVIDENCE_INSUFFICIENT
4. Preservation of AssessmentStatus (generator cannot alter status)
5. Non-legal-advice disclaimer enforcement
6. Status-specific explanation templates (all 8 assessment states)
"""

from datetime import date
from decimal import Decimal
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest

from ai.app.assessment.contracts import (
    AssessmentFinding,
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    EpistemicLayer,
    EvidenceItem,
    EvidenceType,
)
from ai.app.evaluation.assessment_cases import make_retrieval_result
from ai.app.generation.citation_renderer import CitationRenderer
from ai.app.generation.generator import AuditableResponseGenerator
from ai.app.generation.validator import GenerationValidator
from ai.app.retrieval.contracts import RetrievalResponse


def test_generation_grounded_response():
    """Verify generated response contains valid inline and regulatory citations."""
    prov = make_retrieval_result(
        provision_id="prov_sebi_ceiling_15",
        provision_text="Depository participant charges shall not exceed ₹15 per debit.",
        authority="SEBI",
        source_class="REGULATORY",
        document_id="doc_sebi_01",
        citation="SEBI Master Circular 2024",
    )
    retrieval = RetrievalResponse(results=[prov], total_candidates_found=1)

    assessment = AssessmentResult(
        case_id="CASE-1",
        status=AssessmentStatus.VIOLATION_CONFIRMED,
        findings=[
            AssessmentFinding(
                finding_id="F1",
                epistemic_layer=EpistemicLayer.ASSESSED,
                normative_source="REGULATORY",
                status=AssessmentStatus.VIOLATION_CONFIRMED,
                statement="Charged amount ₹25.00 exceeds permitted maximum rate of ₹15.00.",
                provision_ids=[prov.provision_id],
            )
        ],
    )

    generator = AuditableResponseGenerator()
    resp = generator.generate_response(assessment, retrieval)

    assert resp.assessment_status == AssessmentStatus.VIOLATION_CONFIRMED
    assert resp.validation_passed is True
    assert len(resp.regulatory_basis) > 0
    assert resp.regulatory_basis[0].provision_id == prov.provision_id
    assert len(resp.disclaimers) > 0
    assert "does not constitute a formal order" in resp.disclaimers[0]


def test_llm_polish_rewrites_summary_without_changing_assessment():
    assessment = AssessmentResult(
        case_id="CASE-POLISH",
        status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        missing_information=["charged_amount"],
    )
    retrieval = RetrievalResponse(results=[], total_candidates_found=0)
    provider = AsyncMock()
    provider.generate.return_value = SimpleNamespace(
        content="I understand the concern. Please share the exact amount deducted so we can assess it."
    )
    generator = AuditableResponseGenerator(llm_provider=provider)
    response = generator.generate_response(assessment, retrieval)
    original_status = response.assessment_status

    used_polish = asyncio.run(
        generator.polish_summary(
            response,
            assessment,
            retrieval,
            user_question="Why did my holdings decrease?",
        )
    )

    assert used_polish is True
    assert "exact amount deducted" in response.summary
    assert response.assessment_status == original_status


def test_llm_polish_falls_back_when_provider_fails():
    assessment = AssessmentResult(
        case_id="CASE-POLISH-FALLBACK",
        status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        missing_information=["charged_amount"],
    )
    retrieval = RetrievalResponse(results=[], total_candidates_found=0)
    provider = AsyncMock()
    provider.generate.side_effect = TimeoutError("local model unavailable")
    generator = AuditableResponseGenerator(llm_provider=provider)
    response = generator.generate_response(assessment, retrieval)
    original_summary = response.summary

    used_polish = asyncio.run(
        generator.polish_summary(
            response,
            assessment,
            retrieval,
            user_question="Why did my holdings decrease?",
        )
    )

    assert used_polish is False
    assert response.summary == original_summary


def test_generation_rejects_hallucinated_citation():
    """Verify validator flags any hallucinated citation not in retrieved candidates."""
    prov_real = make_retrieval_result(
        provision_id="prov_real",
        document_id="doc_real",
    )
    retrieval = RetrievalResponse(results=[prov_real], total_candidates_found=1)

    assessment = AssessmentResult(
        case_id="CASE-HALLUCINATE",
        status=AssessmentStatus.VIOLATION_CONFIRMED,
        findings=[
            AssessmentFinding(
                finding_id="F1",
                epistemic_layer=EpistemicLayer.ASSESSED,
                normative_source="REGULATORY",
                status=AssessmentStatus.VIOLATION_CONFIRMED,
                statement="Violation under imaginary circular.",
                # Imaginary provision not present in retrieval!
                provision_ids=["prov_imaginary_fake_123"],
            )
        ],
    )

    generator = AuditableResponseGenerator()
    resp = generator.generate_response(assessment, retrieval)

    # Post-generation validation must fail
    assert resp.validation_passed is False
    assert any("INVALID_CITATION" in err for err in resp.validation_errors)


def test_generation_rejects_unsupported_claim():
    """Verify validator flags claims asserting facts that were flagged as missing evidence."""
    prov = make_retrieval_result(provision_id="prov_1", document_id="doc_1")
    retrieval = RetrievalResponse(results=[prov], total_candidates_found=1)

    assessment = AssessmentResult(
        case_id="CASE-UNSUPPORTED",
        status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
        missing_information=["transaction_type"],
    )

    generator = AuditableResponseGenerator()
    resp = generator.generate_response(assessment, retrieval)

    # Artificially inject an unsupported factual assertion
    resp.summary += " However it was a delivery transaction."
    val_res = GenerationValidator.validate(resp, assessment, retrieval)

    assert val_res.is_valid is False
    assert any("UNSUPPORTED_CLAIM" in err for err in val_res.errors)


def test_generation_preserves_assessment_status():
    """Verify status mutation is blocked by validator."""
    prov = make_retrieval_result(provision_id="prov_1", document_id="doc_1")
    retrieval = RetrievalResponse(results=[prov], total_candidates_found=1)

    assessment = AssessmentResult(
        case_id="CASE-STATUS",
        status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
    )

    generator = AuditableResponseGenerator()
    resp = generator.generate_response(assessment, retrieval)

    # Attempt to illegally mutate status in generator output
    resp.assessment_status = AssessmentStatus.VIOLATION_CONFIRMED
    val_res = GenerationValidator.validate(resp, assessment, retrieval)

    assert val_res.is_valid is False
    assert any("STATUS_MUTATION_ERROR" in err for err in val_res.errors)
