"""Comprehensive tests for SANGYAN Provision Extraction and Normalization.

Tests all 10 Gold Cases (Section 30):
Case 1: Rule / Obligation
Case 2: Condition preservation
Case 3: Exception preservation
Case 4: Ordered Procedure
Case 5: Explicit Timeline
Case 6: Definition
Case 7: Cross-Reference
Case 8: Fee / Charge
Case 9: Organisation Policy
Case 10: Organisation FAQ

Also verifies:
- Exact substring invariant & source span validation
- Rejection of paraphrased/altered source text
- Rejection of fabricated authorities/dates
- Idempotent extraction
- LLM extractor with structured schema
"""

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from ai.app.extraction.boundaries import detect_candidate_spans
from ai.app.extraction.extractor import (
    DeterministicProvisionExtractor,
    LLMProvisionExtractor,
)
from ai.app.extraction.pipeline import ProvisionExtractionPipeline
from ai.app.extraction.rules import (
    classify_provision_type,
    extract_conditions,
    extract_cross_references,
    extract_definitions,
    extract_exceptions,
    extract_fees,
    extract_procedures,
    extract_timelines,
)
from ai.app.extraction.validator import ProvisionValidator
from ai.app.ingestion.pipeline import InMemoryKnowledgeRepository
from ai.app.knowledge.provisions import (
    Condition,
    ExceptionClause,
    Provision,
    ProvisionType,
    Timeline,
)
from ai.app.knowledge.source_classes import SourceClass
from ai.app.knowledge.temporal import SupersededStatus
from ai.app.models.provider import LLMProvider
from ai.app.models.schemas import LLMResponse


# =====================================================================
# Gold Cases (Section 30)
# =====================================================================

def test_gold_case_01_rule_obligation():
    """Case 1: Mandatory requirement -> RULE or OBLIGATION."""
    text = "The stock broker shall maintain books of account and documents for a period of eight years."
    prov_type = classify_provision_type(text, heading="Record Keeping", source_class=SourceClass.REGULATORY)
    assert prov_type in (ProvisionType.RULE, ProvisionType.OBLIGATION)


def test_gold_case_02_condition():
    """Case 2: Requirement dependent on explicit condition -> Condition preserved."""
    text = "Where the investor submits a valid request, the intermediary shall process the transmission within 21 days."
    conditions = extract_conditions(text)
    assert len(conditions) >= 1
    assert "where the investor submits a valid request" in conditions[0].condition_text.lower()


def test_gold_case_03_exception():
    """Case 3: Rule containing explicit exception -> Exception preserved."""
    text = "The depository participant shall process transfer instructions immediately, except where an attachment order is in force."
    exceptions = extract_exceptions(text)
    assert len(exceptions) >= 1
    assert "except where an attachment order is in force" in exceptions[0].exception_text.lower()


def test_gold_case_04_procedure():
    """Case 4: Multi-step grievance procedure -> Ordered procedure."""
    text = (
        "Level 1: Investor should first approach the intermediary.\n"
        "Level 2: If unresolved within 30 days, the investor may lodge a complaint on SCORES."
    )
    steps = extract_procedures(text)
    assert len(steps) >= 2
    assert steps[0].step_number == 1
    assert steps[1].step_number == 2
    assert steps[1].escalation_path == "SCORES"


def test_gold_case_05_timeline():
    """Case 5: 'within 30 working days' -> duration=30, unit=DAYS, qualifier=WORKING_DAYS."""
    text = "The intermediary shall resolve all investor grievances within 30 working days from receipt."
    timelines = extract_timelines(text)
    assert len(timelines) >= 1
    tl = timelines[0]
    assert tl.duration == 30
    assert tl.unit == "DAYS"
    assert tl.qualifier == "WORKING_DAYS"


def test_gold_case_06_definition():
    """Case 6: Defined regulatory term -> DEFINITION."""
    text = '"Depository Participant" means a person registered as such under subsection (1A) of section 12 of the SEBI Act.'
    definitions = extract_definitions(text)
    assert len(definitions) >= 1
    d = definitions[0]
    assert d.defined_term == "Depository Participant"
    assert "subsection (1A) of section 12" in d.definition_text


def test_gold_case_07_cross_reference():
    """Case 7: Explicit reference to another regulation/section -> REFERENCES."""
    text = "The listed entity shall comply with disclosure requirements specified under Regulation 30(4) of the LODR Regulations."
    cross_refs = extract_cross_references(text)
    assert len(cross_refs) >= 1
    assert any("Regulation 30" in cr.target_reference for cr in cross_refs)
    assert cross_refs[0].relationship_type == "REFERENCES"
    assert cross_refs[0].resolved_status == "CROSS_REFERENCE_UNRESOLVED"


def test_gold_case_08_fee_or_charge():
    """Case 8: Explicit fee/charge -> FEE_OR_CHARGE."""
    text = "DP transaction charges shall be ₹13.50 per transaction plus GST."
    fees = extract_fees(text)
    assert len(fees) >= 1
    f = fees[0]
    assert f.amount == 13.50
    assert f.currency == "INR"
    assert "per transaction" in f.unit.lower()


def test_gold_case_09_organisation_policy():
    """Case 9: Broker charge schedule -> ORGANISATION_POLICY."""
    text = "Zerodha brokerage charges for equity intraday trades are 0.03% or ₹20 per executed order, whichever is lower."
    prov_type = classify_provision_type(text, heading="Brokerage Schedule", source_class=SourceClass.ORGANISATION_POLICY)
    assert prov_type == ProvisionType.FEE_OR_CHARGE


def test_gold_case_10_organisation_faq():
    """Case 10: Broker FAQ -> ORGANISATION_FAQ."""
    text = "How long does demat transfer take? Demat transfers are usually processed within 48 hours of instruction slip submission."
    prov_type = classify_provision_type(text, heading="Frequently Asked Questions", source_class=SourceClass.ORGANISATION_FAQ)
    assert prov_type in (ProvisionType.GENERAL_INFORMATION, ProvisionType.PROCEDURE, ProvisionType.TIMELINE)


# =====================================================================
# Invariant & Deterministic Validation Tests (Section 17 & 18)
# =====================================================================

def test_source_span_exact_substring():
    """Verify source_start and source_end point to exact substring in parent content."""
    content = (
        "1. Preliminary Guidelines\n\n"
        "2. The stock broker shall appoint a compliance officer who shall monitor statutory compliance.\n\n"
        "3. Failure to comply shall attract penalty."
    )
    spans = detect_candidate_spans(content)
    assert len(spans) >= 2
    for s in spans:
        assert content[s.start_idx:s.end_idx] == s.text


def test_validation_rejects_altered_source_text():
    """Section 17: Paraphrased or altered source text must be rejected."""
    section_content = "The stock broker shall resolve the investor grievance within 30 days."
    paraphrased_text = "Brokers must fix complaints fast."  # Forbidden summary

    prov = Provision(
        provision_id="prov_test_01",
        document_id="doc_sebi_001",
        section_id="sec_1",
        provision_type=ProvisionType.OBLIGATION,
        source_text=paraphrased_text,
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
    )
    res = ProvisionValidator.validate_provision(
        provision=prov,
        section_content=section_content,
        expected_document_id="doc_sebi_001",
        expected_authority="SEBI",
        expected_source_class=SourceClass.REGULATORY,
    )
    assert res.is_valid is False
    assert any("NOT an exact substring" in err for err in res.errors)


def test_validation_rejects_invented_authority():
    """Section 17: Cannot invent or alter authority."""
    section_content = "The trading member shall execute orders strictly as instructed."
    prov = Provision(
        provision_id="prov_test_02",
        document_id="doc_sebi_001",
        section_id="sec_1",
        provision_type=ProvisionType.OBLIGATION,
        source_text="The trading member shall execute orders strictly as instructed.",
        authority="INVENTED_AUTHORITY",
        source_class=SourceClass.REGULATORY,
    )
    res = ProvisionValidator.validate_provision(
        provision=prov,
        section_content=section_content,
        expected_document_id="doc_sebi_001",
        expected_authority="SEBI",
        expected_source_class=SourceClass.REGULATORY,
    )
    assert res.is_valid is False
    assert any("authority mismatch" in err for err in res.errors)


def test_validation_rejects_inverted_dates():
    """Termination date cannot precede effective date."""
    section_content = "All trading members shall comply with this directive."
    prov = Provision(
        provision_id="prov_test_03",
        document_id="doc_sebi_001",
        section_id="sec_1",
        provision_type=ProvisionType.RULE,
        source_text="All trading members shall comply with this directive.",
        authority="SEBI",
        source_class=SourceClass.REGULATORY,
        effective_date=date(2026, 6, 1),
        termination_date=date(2025, 1, 1),  # Invalid
    )
    res = ProvisionValidator.validate_provision(
        provision=prov,
        section_content=section_content,
        expected_document_id="doc_sebi_001",
        expected_authority="SEBI",
        expected_source_class=SourceClass.REGULATORY,
    )
    assert res.is_valid is False
    assert any("termination_date" in err for err in res.errors)


@pytest.mark.asyncio
async def test_idempotent_extraction_pipeline():
    """Section 28: Running extraction twice produces identical deterministic IDs."""
    repo = InMemoryKnowledgeRepository()
    extractor = DeterministicProvisionExtractor()
    pipeline = ProvisionExtractionPipeline(extractor=extractor, repository=repo)

    section_data = [
        {
            "id": 1,
            "document_id": "doc_test_001",
            "section_key": "sec_1",
            "heading": "Grievance Procedure",
            "content": "The broker shall acknowledge the complaint within 24 hours.",
        }
    ]
    meta_map = {
        "doc_test_001": {
            "authority": "SEBI",
            "organisation_id": None,
            "source_class": SourceClass.REGULATORY,
            "source_url": "https://sebi.gov.in/doc.pdf",
            "source_hash": "a" * 64,
        }
    }

    # Run 1
    provisions_1, metrics_1 = await pipeline.run_pipeline_on_sections(section_data, meta_map)
    assert len(provisions_1) == 1
    prov_id_1 = provisions_1[0].provision_id

    # Run 2
    provisions_2, metrics_2 = await pipeline.run_pipeline_on_sections(section_data, meta_map)
    assert len(provisions_2) == 1
    prov_id_2 = provisions_2[0].provision_id

    # Identical IDs
    assert prov_id_1 == prov_id_2
    stored_provisions = await repo.list_provisions_by_document("doc_test_001")
    assert len(stored_provisions) == 1, "Duplicate provision must NOT be inserted into repository"


@pytest.mark.asyncio
async def test_llm_extractor_fallback_on_invalid_output():
    """Verify that if LLM provider returns invalid substring, fallback to exact deterministic span occurs."""
    mock_provider = AsyncMock(spec=LLMProvider)
    # LLM hallucinates non-matching source text
    mock_provider.generate.return_value = LLMResponse(
        content=json.dumps({
            "provisions": [
                {
                    "source_text": "Hallucinated altered text not in source",
                    "provision_type": "RULE",
                }
            ]
        }),
        model="mock_model",
        provider="mock_provider",
        latency_ms=10.0,
    )

    extractor = LLMProvisionExtractor(provider=mock_provider)
    section_content = "The depository participant shall process the rematerialisation request within 30 days."

    provisions = await extractor.extract_provisions(
        section_key="sec_1",
        section_heading="Rematerialisation",
        section_content=section_content,
        document_id="doc_cdsl_001",
        authority="CDSL",
        organisation_id=None,
        source_class=SourceClass.REGULATORY,
        canonical_url="https://cdslindia.com/remat.html",
        source_hash="b" * 64,
    )

    assert len(provisions) >= 1
    # Fallback guaranteed exact substring from section_content
    for p in provisions:
        assert p.source_text in section_content
        assert p.authority == "CDSL"
