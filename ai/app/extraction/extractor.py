"""Evidentiary Fact Extractor for SANGYAN Complaints and Documents.

Epistemic foundation:
- Extracts structured empirical facts with exact source spans and offsets.
- Classifies epistemic origin: USER_ASSERTED, DOCUMENT_ASSERTED, DERIVED, MODEL_INTERPRETATION.
- STRICT SAFETY RULE: Never extract legal conclusions (e.g. 'violation = true').
- If input asserts "I think Zerodha overcharged me", extracts user_belief='overcharged', NEVER a legal violation.
- Detects contradictory assertions between narrative and documents.
- Produces candidate evidence proposals without directly mutating authoritative case state.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import logging
import re
from typing import Any
import uuid

from ai.app.assessment.contracts import (
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceType,
)
from ai.app.extraction.contracts import (
    ExtractionSupportLevel,
    ExtractedFact,
    FactEpistemicStatus,
    FactExtractionRequest,
    FactExtractionResult,
    FactType,
    SourceSpan,
)
from ai.app.extraction.fact_normalizer import FactNormalizer
from ai.app.extraction.provision_extractor import (
    DeterministicProvisionExtractor,
    LLMProvisionExtractor,
    ProvisionExtractor,
)
from ai.app.models.provider import LLMProvider

logger = logging.getLogger("sangyan.extraction.extractor")


class FactExtractor:
    """Extracts typed empirical facts from complaints, narratives, and uploaded documents."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider

    def extract(self, request: FactExtractionRequest) -> FactExtractionResult:
        """Extract structured facts and evidence proposals from input payload."""
        text = request.input_text
        source_id = request.source_id
        ref_date = request.reference_date
        source_type = request.source_type

        default_status = (
            FactEpistemicStatus.DOCUMENT_ASSERTED
            if source_type in {EvidenceType.DOCUMENT, EvidenceType.TRANSACTION_RECORD, EvidenceType.BROKER_STATEMENT, EvidenceType.INVOICE}
            else FactEpistemicStatus.USER_ASSERTED
        )

        extracted_facts: list[ExtractedFact] = []
        warnings: list[str] = []
        contradictions: list[str] = []

        # 1. Extract Organisation / Intermediary
        org_facts = self._extract_organisation(text, source_id, default_status)
        extracted_facts.extend(org_facts)

        # 2. Extract Monetary Amounts & Fees
        fee_facts = self._extract_monetary_amounts(text, source_id, default_status)
        extracted_facts.extend(fee_facts)

        # 3. Extract Dates
        date_facts, date_warnings = self._extract_dates(text, source_id, default_status, ref_date)
        extracted_facts.extend(date_facts)
        warnings.extend(date_warnings)

        # 4. Extract Transaction Type & Action
        txn_facts = self._extract_transaction_types(text, source_id, default_status)
        extracted_facts.extend(txn_facts)

        # 5. Extract Quantity and Instrument if present
        meta_facts = self._extract_instrument_and_quantity(text, source_id, default_status)
        extracted_facts.extend(meta_facts)

        # 6. Extract User Allegations / Beliefs (Preserved as USER_ASSERTED, NOT as a legal conclusion)
        belief_facts = self._extract_user_beliefs(text, source_id)
        extracted_facts.extend(belief_facts)

        # 7. Check for Contradictory Evidence inside input (e.g. multiple distinct charged amounts)
        amounts = [f for f in extracted_facts if f.field == "charged_amount"]
        if len(amounts) > 1:
            unique_vals = {a.normalized_value for a in amounts if a.normalized_value is not None}
            if len(unique_vals) > 1:
                contradiction_desc = (
                    f"Contradictory charged amounts found in input: {', '.join(str(v) for v in unique_vals)}"
                )
                contradictions.append(contradiction_desc)
                for a in amounts:
                    a.epistemic_status = FactEpistemicStatus.CONTRADICTORY_EVIDENCE

        # 8. Check for Compound Tax / GST derivation
        gst_facts = self._detect_gst_breakdown(amounts, text, source_id)
        extracted_facts.extend(gst_facts)

        # 9. Synthesize EvidenceItem proposals and Candidate Case Facts
        evidence_proposals, case_fact_candidates = self._synthesize_proposals(
            extracted_facts, source_id, source_type, ref_date
        )

        extraction_id = f"EXT-{uuid.uuid4().hex[:12]}"
        return FactExtractionResult(
            extraction_id=extraction_id,
            source_id=source_id,
            extracted_facts=extracted_facts,
            evidence_proposals=evidence_proposals,
            case_fact_candidates=case_fact_candidates,
            contradictions=contradictions,
            unresolved_fields=[] if "charged_amount" in case_fact_candidates else ["charged_amount"],
            extraction_warnings=warnings,
        )

    def _extract_organisation(
        self,
        text: str,
        source_id: str,
        epistemic_status: FactEpistemicStatus,
    ) -> list[ExtractedFact]:
        """Detect and normalize known financial intermediaries."""
        facts: list[ExtractedFact] = []
        for alias, org_id in [
            ("zerodha", "ORG_ZERODHA"),
            ("kite", "ORG_ZERODHA"),
            ("ज़ेरोधा", "ORG_ZERODHA"),
            ("angel one", "ORG_ANGELONE"),
            ("angel broking", "ORG_ANGELONE"),
            ("angelone", "ORG_ANGELONE"),
            ("groww", "ORG_GROWW"),
            ("ग्रो", "ORG_GROWW"),
            ("upstox", "ORG_UPSTOX"),
            ("अपस्टॉक्स", "ORG_UPSTOX"),
            ("icici direct", "ORG_ICICIDIRECT"),
            ("icicidirect", "ORG_ICICIDIRECT"),
            ("icici securities", "ORG_ICICIDIRECT"),
        ]:
            if any(ord(c) > 127 for c in alias):
                match = re.search(re.escape(alias), text, re.IGNORECASE)
            else:
                match = re.search(rf"\b{re.escape(alias)}\b", text, re.IGNORECASE)
            if match:
                span_text = match.group(0)
                facts.append(
                    ExtractedFact(
                        field="organisation",
                        raw_value=span_text,
                        normalized_value=org_id,
                        fact_type=FactType.ENTITY,
                        source_span=SourceSpan(
                            text=span_text,
                            start_char=match.start(),
                            end_char=match.end(),
                            document_id=source_id,
                        ),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ENTITY_DICTIONARY",
                    )
                )
                break  # Pick first primary organisation mention
        return facts

    def _extract_monetary_amounts(
        self,
        text: str,
        source_id: str,
        epistemic_status: FactEpistemicStatus,
    ) -> list[ExtractedFact]:
        """Extract currency amounts using FactNormalizer."""
        facts: list[ExtractedFact] = []
        # Matches e.g. ₹15.93, Rs. 15.93, INR 15.93, 15.93 rupees, 15.93 रुपये
        pattern = r"(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)\s*(?:rupees?|रुपये|रुपए)?"

        for match in re.finditer(pattern, text, re.IGNORECASE):
            full_match = match.group(0)
            leading_ws = len(full_match) - len(full_match.lstrip())
            trailing_ws = len(full_match) - len(full_match.rstrip())
            raw_match = full_match.strip()
            num_part = match.group(1).strip()
            start_pos = match.start() + leading_ws
            end_pos = match.end() - trailing_ws

            # Avoid false positives on single isolated small integers unless currency marked
            has_currency_marker = any(m in raw_match.lower() for m in ["₹", "rs", "inr", "rupee", "रुपये", "रुपए"])
            if not has_currency_marker and "." not in num_part:
                continue

            amt, curr = FactNormalizer.normalize_currency(raw_match)
            if amt is not None and amt > Decimal("0.00"):
                facts.append(
                    ExtractedFact(
                        field="charged_amount",
                        raw_value=raw_match,
                        normalized_value=amt,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(
                            text=raw_match,
                            start_char=start_pos,
                            end_char=end_pos,
                            document_id=source_id,
                        ),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="CURRENCY_PARSER",
                    )
                )
        return facts

    def _extract_dates(
        self,
        text: str,
        source_id: str,
        epistemic_status: FactEpistemicStatus,
        reference_date: date | None,
    ) -> tuple[list[ExtractedFact], list[str]]:
        """Extract event/transaction dates."""
        facts: list[ExtractedFact] = []
        warnings: list[str] = []

        # Candidate regexes for dates
        patterns = [
            r"(\d{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+,?\s+\d{4})",  # 12 September 2026
            r"(\d{1,2}\s+[a-zA-Z]+)",                            # 12 September (without year)
            r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})",                  # 2026-09-12
            r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})",                  # 12/09/2026
            r"(\d{1,2}\s+(?:जनवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|अक्टूबर|नवंबर|दिसंबर)\s+\d{4})",  # Hindi date
            r"\b(yesterday|today|कल|आज)\b",
        ]

        found_spans: set[tuple[int, int]] = set()

        for pat in patterns:
            for match in re.finditer(pat, text, re.IGNORECASE):
                span = (match.start(), match.end())
                if span in found_spans:
                    continue
                found_spans.add(span)

                raw_span = match.group(0)
                parsed_date = FactNormalizer.normalize_date(raw_span, reference_date)

                # If year was omitted (e.g. "12 September"), infer from reference_date if available
                if parsed_date is None and reference_date and not any(char.isdigit() and len(raw_span.split()[-1]) == 4 for char in raw_span):
                    tentative = f"{raw_span} {reference_date.year}"
                    parsed_date = FactNormalizer.normalize_date(tentative, reference_date)

                if parsed_date is not None:
                    facts.append(
                        ExtractedFact(
                            field="transaction_date",
                            raw_value=raw_span,
                            normalized_value=parsed_date,
                            fact_type=FactType.DATE,
                            source_span=SourceSpan(
                                text=raw_span,
                                start_char=match.start(),
                                end_char=match.end(),
                                document_id=source_id,
                            ),
                            epistemic_status=epistemic_status,
                            confidence=ExtractionSupportLevel.DIRECT,
                            extraction_method="DATE_PARSER",
                        )
                    )
                elif raw_span.lower() in {"yesterday", "कल", "today", "आज"}:
                    warnings.append(
                        f"Relative date '{raw_span}' could not be resolved: no reference_date provided."
                    )

        return facts, warnings

    def _extract_transaction_types(
        self,
        text: str,
        source_id: str,
        epistemic_status: FactEpistemicStatus,
    ) -> list[ExtractedFact]:
        """Identify transaction type (e.g. equity_delivery, intraday, amc)."""
        facts: list[ExtractedFact] = []
        for kw, canonical in [
            ("sold shares", "equity_delivery"),
            ("sell shares", "equity_delivery"),
            ("selling shares", "equity_delivery"),
            ("delivery sale", "equity_delivery"),
            ("equity delivery", "equity_delivery"),
            ("shares sold", "equity_delivery"),
            ("share becha", "equity_delivery"),
            ("शेयर बेचे", "equity_delivery"),
            ("बिक्री", "equity_delivery"),
            ("becha", "equity_delivery"),
            ("selling", "equity_delivery"),
            ("delivery", "equity_delivery"),
            ("sold", "equity_delivery"),
            ("sell", "equity_delivery"),
            ("intraday", "intraday"),
            ("amc", "amc"),
            ("maintenance", "amc"),
            ("bsda", "bsda"),
        ]:
            if any(ord(c) > 127 for c in kw):
                match = re.search(re.escape(kw), text, re.IGNORECASE)
            else:
                match = re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE)
            if match:
                raw_span = match.group(0)
                facts.append(
                    ExtractedFact(
                        field="transaction_type",
                        raw_value=raw_span,
                        normalized_value=canonical,
                        fact_type=FactType.ENUM,
                        source_span=SourceSpan(
                            text=raw_span,
                            start_char=match.start(),
                            end_char=match.end(),
                            document_id=source_id,
                        ),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="TRANSACTION_KEYWORD",
                    )
                )
                break
        return facts

    def _extract_instrument_and_quantity(
        self,
        text: str,
        source_id: str,
        epistemic_status: FactEpistemicStatus,
    ) -> list[ExtractedFact]:
        """Extract share quantity and instrument ticker if present."""
        facts: list[ExtractedFact] = []
        # Match e.g. "10 shares of ABC" or "sold 50 ITC"
        match = re.search(r"(\d+)\s+shares?(?:\s+of\s+([A-Z0-9\-_]+))?", text, re.IGNORECASE)
        if match:
            qty_span = match.group(1)
            facts.append(
                ExtractedFact(
                    field="quantity",
                    raw_value=qty_span,
                    normalized_value=int(qty_span),
                    fact_type=FactType.INTEGER,
                    source_span=SourceSpan(
                        text=qty_span,
                        start_char=match.start(1),
                        end_char=match.end(1),
                        document_id=source_id,
                    ),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="REGEX",
                )
            )
            if match.group(2):
                inst_span = match.group(2)
                facts.append(
                    ExtractedFact(
                        field="instrument",
                        raw_value=inst_span,
                        normalized_value=inst_span.upper(),
                        fact_type=FactType.STRING,
                        source_span=SourceSpan(
                            text=inst_span,
                            start_char=match.start(2),
                            end_char=match.end(2),
                            document_id=source_id,
                        ),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="REGEX",
                    )
                )
        return facts

    def _extract_user_beliefs(
        self,
        text: str,
        source_id: str,
    ) -> list[ExtractedFact]:
        """Extract subjective allegations without converting them to legal conclusions."""
        facts: list[ExtractedFact] = []
        belief_patterns = [
            r"(too high|illegal|overcharged|fraud|scam|unfair|wrongly deducted|गलत काटा|धोखा)",
        ]
        for pat in belief_patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                raw_span = match.group(0)
                facts.append(
                    ExtractedFact(
                        field="user_allegation",
                        raw_value=raw_span,
                        normalized_value=raw_span.lower(),
                        fact_type=FactType.STRING,
                        source_span=SourceSpan(
                            text=raw_span,
                            start_char=match.start(),
                            end_char=match.end(),
                            document_id=source_id,
                        ),
                        epistemic_status=FactEpistemicStatus.USER_ASSERTED,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="SUBJECTIVE_SPAN",
                        notes="Subjective user belief. MUST NOT be treated as a legal violation.",
                    )
                )
        return facts

    def _detect_gst_breakdown(
        self,
        amount_facts: list[ExtractedFact],
        text: str,
        source_id: str,
    ) -> list[ExtractedFact]:
        """Detect compound GST component (e.g. 15.93 = 13.50 + 18% GST)."""
        facts: list[ExtractedFact] = []
        for af in amount_facts:
            amt = af.normalized_value
            if isinstance(amt, Decimal) and FactNormalizer.detect_compound_gst(amt, Decimal("13.50")):
                facts.append(
                    ExtractedFact(
                        field="gst_breakdown",
                        raw_value=str(amt),
                        normalized_value={"base_tariff": Decimal("13.50"), "gst_rate": Decimal("0.18"), "total": amt},
                        fact_type=FactType.PERCENTAGE,
                        source_span=af.source_span,
                        epistemic_status=FactEpistemicStatus.DERIVED,
                        confidence=ExtractionSupportLevel.STRONGLY_SUPPORTED,
                        extraction_method="GST_DERIVATION",
                        notes="Derived: ₹15.93 comprises base DP charge ₹13.50 + 18% GST (₹2.43).",
                    )
                )
        return facts

    def _synthesize_proposals(
        self,
        facts: list[ExtractedFact],
        source_id: str,
        source_type: EvidenceType,
        ref_date: date | None,
    ) -> tuple[list[EvidenceItem], dict[str, Any]]:
        """Construct candidate EvidenceItems and candidate case facts."""
        proposals: list[EvidenceItem] = []
        candidates: dict[str, Any] = {}

        for fact in facts:
            # Map fact to EvidenceItem
            ev_id = f"EVID-PROP-{fact.field.upper()}-{uuid.uuid4().hex[:6]}"
            proposals.append(
                EvidenceItem(
                    evidence_id=ev_id,
                    case_id="PROPOSED_CASE",
                    evidence_type=source_type,
                    field_name=fact.field,
                    value=fact.normalized_value,
                    source=source_id,
                    confidence=EpistemicSupportLevel.HIGH_SUPPORT if fact.confidence == ExtractionSupportLevel.DIRECT else EpistemicSupportLevel.MODERATE_SUPPORT,
                    provenance={"source_span": fact.source_span.model_dump(), "method": fact.extraction_method},
                )
            )

            # Record latest canonical candidate fact
            if fact.field in {"charged_amount", "transaction_date", "organisation", "transaction_type", "quantity", "gst_breakdown"}:
                candidates[fact.field] = fact.normalized_value

        return proposals, candidates
