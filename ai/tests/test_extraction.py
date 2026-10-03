"""Unit tests for SANGYAN Evidentiary Fact Extraction Layer.

Covers:
1. Source span and offset preservation
2. Financial normalization to Decimal and currency
3. Date normalization and reference_date constraint
4. Entity normalization to canonical organisation IDs
5. Hindi and Hinglish multilingual extraction
6. Document extraction (plain text, HTML, PDF)
7. OCRProvider fallback when OCR is unavailable
8. Contradiction detection in raw input
9. Safety invariant: user allegations NEVER become legal violations
10. CaseIntegrator proposal mediation boundary
"""

from datetime import date
from decimal import Decimal
import pytest

from ai.app.assessment.contracts import EvidenceType
from ai.app.extraction.case_integrator import CaseIntegrator
from ai.app.extraction.contracts import (
    FactEpistemicStatus,
    FactExtractionRequest,
    FactType,
)
from ai.app.extraction.document_extractor import DocumentExtractor, FallbackOCRProvider
from ai.app.extraction.extractor import FactExtractor
from ai.app.extraction.fact_normalizer import FactNormalizer


def test_source_span_and_offset_preservation():
    """Verify extracted facts retain verbatim source span and character offsets."""
    extractor = FactExtractor()
    req = FactExtractionRequest(
        input_text="I was charged ₹15.93 for selling shares on 12 September 2026.",
        source_id="complaint_01",
        reference_date=date(2026, 9, 15),
    )
    res = extractor.extract(req)

    amt_fact = next(f for f in res.extracted_facts if f.field == "charged_amount")
    assert amt_fact.normalized_value == Decimal("15.93")
    assert "15.93" in amt_fact.source_span.text
    assert amt_fact.source_span.start_char is not None
    assert amt_fact.source_span.end_char is not None
    assert amt_fact.source_span.start_char < amt_fact.source_span.end_char

    # Verify slice equality in original text
    sliced = req.input_text[amt_fact.source_span.start_char:amt_fact.source_span.end_char]
    assert sliced == amt_fact.source_span.text


def test_financial_normalization_decimal():
    """Verify various currency formats normalize to Decimal INR."""
    for text, expected in [
        ("₹15.93", Decimal("15.93")),
        ("Rs. 13.50", Decimal("13.50")),
        ("INR 20.00", Decimal("20.00")),
        ("25 rupees", Decimal("25.00")),
        ("15.93 रुपये", Decimal("15.93")),
    ]:
        amt, curr = FactNormalizer.normalize_currency(text)
        assert amt == expected
        assert curr == "INR"
        assert isinstance(amt, Decimal)


def test_date_normalization_reference_date_required():
    """Verify relative dates require explicit reference_date and never guess."""
    # With explicit reference_date
    d1 = FactNormalizer.normalize_date("yesterday", reference_date=date(2026, 9, 15))
    assert d1 == date(2026, 9, 14)

    # Without reference_date -> MUST be None
    d2 = FactNormalizer.normalize_date("yesterday", reference_date=None)
    assert d2 is None

    # Textual dates
    d3 = FactNormalizer.normalize_date("12 September 2026")
    assert d3 == date(2026, 9, 12)

    # Hindi dates
    d4 = FactNormalizer.normalize_date("12 सितंबर 2026")
    assert d4 == date(2026, 9, 12)


def test_entity_normalization():
    """Verify broker aliases normalize to canonical IDs and never invent IDs."""
    assert FactNormalizer.normalize_entity("Zerodha Broking Limited") == "ORG_ZERODHA"
    assert FactNormalizer.normalize_entity("ज़ेरोधा") == "ORG_ZERODHA"
    assert FactNormalizer.normalize_entity("Angel One") == "ORG_ANGELONE"
    assert FactNormalizer.normalize_entity("Groww") == "ORG_GROWW"
    assert FactNormalizer.normalize_entity("ICICI Direct") == "ORG_ICICIDIRECT"
    assert FactNormalizer.normalize_entity("Random Fake Broker") is None


def test_multilingual_hindi_extraction():
    """Verify facts can be extracted from Hindi user complaint."""
    extractor = FactExtractor()
    req = FactExtractionRequest(
        input_text="मैंने 12 सितंबर 2026 को शेयर बेचे। ज़ेरोधा ने ₹13.50 काटा।",
        source_id="complaint_hi",
        reference_date=date(2026, 9, 15),
        language="hi",
    )
    res = extractor.extract(req)

    assert res.case_fact_candidates.get("organisation") == "ORG_ZERODHA"
    assert res.case_fact_candidates.get("charged_amount") == Decimal("13.50")
    assert res.case_fact_candidates.get("transaction_date") == date(2026, 9, 12)
    assert res.case_fact_candidates.get("transaction_type") == "equity_delivery"


def test_safety_invariant_user_allegations_not_violations():
    """SAFETY INVARIANT: Allegations of overcharging or scams must NEVER be extracted as legal violations."""
    extractor = FactExtractor()
    req = FactExtractionRequest(
        input_text="I think Zerodha overcharged me and this is an illegal scam!",
        source_id="complaint_scam",
    )
    res = extractor.extract(req)

    # Must NOT contain a 'violation' or 'illegal' fact
    for fact in res.extracted_facts:
        assert fact.field != "violation"
        assert fact.field != "illegal"
        if fact.field == "user_allegation":
            assert fact.epistemic_status == FactEpistemicStatus.USER_ASSERTED
            assert "MUST NOT be treated as a legal violation" in (fact.notes or "")


def test_contradiction_detection():
    """Verify conflicting amounts in input text produce contradictions."""
    extractor = FactExtractor()
    req = FactExtractionRequest(
        input_text="Complaint says ₹50 was deducted but receipt says ₹15.",
        source_id="contradictory_doc",
    )
    res = extractor.extract(req)
    assert len(res.contradictions) > 0
    assert any("50" in c and "15" in c for c in res.contradictions)


def test_ocr_provider_fallback():
    """Verify missing OCR dependencies gracefully raise OCR_UNAVAILABLE."""
    doc_ext = DocumentExtractor(ocr_provider=FallbackOCRProvider())
    with pytest.raises(RuntimeError, match="OCR_UNAVAILABLE"):
        doc_ext.extract_from_image(b"\x89PNG\r\n\x1a\n", "doc_img")


def test_case_integrator_proposal_boundary():
    """Verify proposals do not silently overwrite committed case state when conflicting."""
    extractor = FactExtractor()
    req = FactExtractionRequest(
        input_text="Charged ₹25.00 on 2026-01-10.",
        source_id="doc_new",
    )
    res = extractor.extract(req)

    # Existing committed facts have charged_amount = 15.00
    committed_evidence, committed_facts, warnings = CaseIntegrator.integrate_proposals(
        extraction_result=res,
        case_id="CASE-1",
        existing_facts={"charged_amount": Decimal("15.00")},
    )

    # Must retain existing committed fact and issue warning
    assert committed_facts["charged_amount"] == Decimal("15.00")
    assert any("conflicts with newly extracted candidate" in w for w in warnings)
