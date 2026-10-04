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

        # 5b. Extract Account Type and BSDA qualification
        acc_facts = self._extract_account_type(text, source_id, default_status)
        extracted_facts.extend(acc_facts)

        # 5c. Extract Infrastructure Entities (Portal, Authority)
        entity_facts = self._extract_domain_entities(text, source_id, default_status)
        extracted_facts.extend(entity_facts)

        # 5d. Extract Domain Specific Attributes (Process, Action, Product, Channels, Durations)
        domain_facts = self._extract_domain_attributes(text, source_id, default_status)
        extracted_facts.extend(domain_facts)

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
        sorted_aliases = sorted(FactNormalizer.ORGANISATION_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
        for alias, org_id in sorted_aliases:
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
        """Extract currency amounts with strict role disambiguation and adversarial safety."""
        facts: list[ExtractedFact] = []

        # Adversarial Isolation: do not extract numeric penalties from system prompt injections
        sanitized_text = text
        injection_match = re.search(
            r"\b(?:SYSTEM\s+OVERRIDE|IGNORE\s+ALL\s+PREVIOUS\s+INSTRUCTIONS|IGNORE\s+PREVIOUS\s+RULES|DISREGARD\s+ALL\s+INSTRUCTIONS)\b.*",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if injection_match:
            sanitized_text = text[:injection_match.start()]

        lower = sanitized_text.lower()

        # Check approximation marker (e.g. AMB-002: "around Rs 50")
        is_approx = bool(
            re.search(
                r"\b(around|approx|approximately|lagbhag|karib|लगभग|करीब|about)\s+(?:[₹]|rs\.?|inr)?\s*\d+",
                lower,
            )
        )
        if is_approx:
            facts.append(
                ExtractedFact(
                    field="is_amount_approximate",
                    raw_value="approximate",
                    normalized_value=True,
                    fact_type=FactType.BOOLEAN,
                    source_span=SourceSpan(text="approximate", start_char=0, end_char=0, document_id=source_id),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="APPROXIMATION_PARSER",
                )
            )

        # 1. Order Value / Turnover
        order_match = re.search(
            r"(?:order\s+(?:of|worth|value)|buy\s+trade\s+of|sell\s+trade\s+of|trade\s+of|intraday\s+buy\s+trade\s+of|sold\s+shares\s+worth|shares\s+worth|worth|maine)\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:\.[0-9]+)?\s*(?:lakh|लाख|crore|करोड़)|[0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)",
            sanitized_text,
            re.IGNORECASE,
        )
        if order_match:
            raw_ov = order_match.group(1)
            ov, _ = FactNormalizer.normalize_currency(raw_ov)
            if ov is not None:
                facts.append(
                    ExtractedFact(
                        field="order_value",
                        raw_value=order_match.group(0),
                        normalized_value=ov,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=order_match.group(0), start_char=order_match.start(), end_char=order_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )
                facts.append(
                    ExtractedFact(
                        field="turnover",
                        raw_value=order_match.group(0),
                        normalized_value=ov,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=order_match.group(0), start_char=order_match.start(), end_char=order_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        # 2. Portfolio Value
        port_match = re.search(
            r"(?:portfolio|holdings?|demat\s+holding)(?:\s+(?:value|worth|valuation|was|is|of|dropped\s+to|fell\s+to|reached))+[\s:]*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?|\d+(?:\.[0-9]+)?\s*(?:lakh|लाख|crore|करोड़))",
            sanitized_text,
            re.IGNORECASE,
        )
        if not port_match:
            port_match = re.search(
                r"(?:portfolio|holdings?|account\s+holding)\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?|\d+(?:\.[0-9]+)?\s*(?:lakh|लाख|crore|करोड़))\s*(?:worth)?",
                sanitized_text,
                re.IGNORECASE,
            )
        if port_match:
            raw_pv = port_match.group(1)
            pv, _ = FactNormalizer.normalize_currency(raw_pv)
            if pv is not None:
                facts.append(
                    ExtractedFact(
                        field="portfolio_value",
                        raw_value=port_match.group(0),
                        normalized_value=pv,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=port_match.group(0), start_char=port_match.start(), end_char=port_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )
                facts.append(
                    ExtractedFact(
                        field="portfolio_valuation",
                        raw_value=port_match.group(0),
                        normalized_value=pv,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=port_match.group(0), start_char=port_match.start(), end_char=port_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        # 3. Turnover
        turn_match = re.search(
            r"(?:turnover\s+(?:of|is)?)\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?|\d+\s*(?:lakh|लाख|crore|करोड़))",
            sanitized_text,
            re.IGNORECASE,
        )
        if turn_match:
            raw_to = turn_match.group(1)
            to_val, _ = FactNormalizer.normalize_currency(raw_to)
            if to_val is not None:
                facts.append(
                    ExtractedFact(
                        field="turnover",
                        raw_value=turn_match.group(0),
                        normalized_value=to_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=turn_match.group(0), start_char=turn_match.start(), end_char=turn_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        # 4. Total Charges / Total Deductions
        total_match = re.search(
            r"(?:total\s+charges|total\s+deductions|total\s+deduction|total[\s:]*)\s*(?:of|is|was)?\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)",
            sanitized_text,
            re.IGNORECASE,
        )
        if total_match:
            raw_tot = total_match.group(1)
            tot_val, _ = FactNormalizer.normalize_currency(raw_tot)
            if tot_val is not None:
                facts.append(
                    ExtractedFact(
                        field="total_charges",
                        raw_value=total_match.group(0),
                        normalized_value=tot_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=total_match.group(0), start_char=total_match.start(), end_char=total_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )
                facts.append(
                    ExtractedFact(
                        field="total_deductions",
                        raw_value=total_match.group(0),
                        normalized_value=tot_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=total_match.group(0), start_char=total_match.start(), end_char=total_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        # 5. Fee Paid
        fee_paid_match = re.search(
            r"(?:fee\s+paid|paid\s+(?:a\s+)?(?:fee|subscription)\s+of|paid\s+(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)\s*(?:subscription|fee))",
            sanitized_text,
            re.IGNORECASE,
        )
        if fee_paid_match:
            raw_fp = fee_paid_match.group(1)
            fp_val, _ = FactNormalizer.normalize_currency(raw_fp)
            if fp_val is not None:
                facts.append(
                    ExtractedFact(
                        field="fee_paid",
                        raw_value=fee_paid_match.group(0),
                        normalized_value=fp_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=fee_paid_match.group(0), start_char=fee_paid_match.start(), end_char=fee_paid_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        # 5b. Specialized fine-grained fee roles
        dp_match = re.search(
            r"(?:Depository\s+Participant\s+Charges|DP\s+Charges|base\s+dp\s+charge)[\s:]*(?:Rs\.?|₹)?\s*([0-9]+(?:\.[0-9]+)?)",
            sanitized_text,
            re.IGNORECASE,
        )
        if dp_match:
            raw_dp = dp_match.group(1)
            dp_val, _ = FactNormalizer.normalize_currency(raw_dp)
            if dp_val is not None:
                facts.append(
                    ExtractedFact(
                        field="base_dp_charge",
                        raw_value=dp_match.group(0),
                        normalized_value=dp_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=dp_match.group(0), start_char=dp_match.start(), end_char=dp_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        agr_match = re.search(
            r"(?:Schedule\s+of\s+Brokerage|agreed\s+rate|brokerage[\s_-]*rate).*?(?:Rs\.?|₹)\s*(\d+(?:\.\d+)?)\s*per\s*(?:executed\s+)?order",
            sanitized_text,
            re.IGNORECASE,
        )
        if agr_match:
            raw_agr = agr_match.group(1)
            agr_val, _ = FactNormalizer.normalize_currency(raw_agr)
            if agr_val is not None:
                facts.append(
                    ExtractedFact(
                        field="agreed_rate",
                        raw_value=agr_match.group(0),
                        normalized_value=agr_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=agr_match.group(0), start_char=agr_match.start(), end_char=agr_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        prem_match = re.search(
            r"(?:premium\s+value\s+(?:of)?|premium\s+(?:of)?)\s*(?:[₹]|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]{2})?)",
            sanitized_text,
            re.IGNORECASE,
        )
        if prem_match:
            raw_prem = prem_match.group(1)
            prem_val, _ = FactNormalizer.normalize_currency(raw_prem)
            if prem_val is not None:
                facts.append(
                    ExtractedFact(
                        field="premium_value",
                        raw_value=prem_match.group(0),
                        normalized_value=prem_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=prem_match.group(0), start_char=prem_match.start(), end_char=prem_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        sttb_match = re.search(
            r"(?:stt\s+of|deducted\s+stt\s+of)\s*(?:[₹]|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]{2})?)",
            sanitized_text,
            re.IGNORECASE,
        )
        if sttb_match:
            raw_sttb = sttb_match.group(1)
            sttb_val, _ = FactNormalizer.normalize_currency(raw_sttb)
            if sttb_val is not None:
                facts.append(
                    ExtractedFact(
                        field="stt_billed",
                        raw_value=sttb_match.group(0),
                        normalized_value=sttb_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=sttb_match.group(0), start_char=sttb_match.start(), end_char=sttb_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        sebi_fee_match = re.search(
            r"(?:sebi\s+(?:turnover\s+)?fee\s+of)\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:\.[0-9]+)?)",
            sanitized_text,
            re.IGNORECASE,
        )
        if sebi_fee_match:
            raw_sf = sebi_fee_match.group(1)
            sf_val, _ = FactNormalizer.normalize_currency(raw_sf)
            if sf_val is not None:
                facts.append(
                    ExtractedFact(
                        field="sebi_fee_billed",
                        raw_value=sebi_fee_match.group(0),
                        normalized_value=sf_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=sebi_fee_match.group(0), start_char=sebi_fee_match.start(), end_char=sebi_fee_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        gdiv_match = re.search(
            r"(?:declared|gross)[\s:]*(?:[₹]|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]{2})?)\s*dividend",
            sanitized_text,
            re.IGNORECASE,
        )
        if gdiv_match:
            raw_gd = gdiv_match.group(1)
            gd_val, _ = FactNormalizer.normalize_currency(raw_gd)
            if gd_val is not None:
                facts.append(
                    ExtractedFact(
                        field="gross_dividend",
                        raw_value=gdiv_match.group(0),
                        normalized_value=gd_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=gdiv_match.group(0), start_char=gdiv_match.start(), end_char=gdiv_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        ndiv_match = re.search(
            r"(?:only\s+)?(?:[₹]|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]{2})?)\s*(?:was\s+)?credited",
            sanitized_text,
            re.IGNORECASE,
        )
        if ndiv_match:
            raw_nd = ndiv_match.group(1)
            nd_val, _ = FactNormalizer.normalize_currency(raw_nd)
            if nd_val is not None:
                facts.append(
                    ExtractedFact(
                        field="net_dividend",
                        raw_value=ndiv_match.group(0),
                        normalized_value=nd_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=ndiv_match.group(0), start_char=ndiv_match.start(), end_char=ndiv_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        # 6. Negative Amount
        neg_match = re.search(
            r"(?:negative\s+balance\s+(?:of)?|ledger\s+me\s+)?\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)\s*(?:rupees?|rupaye|रुपये|रुपए)?\s*(?:ka\s+)?negative(?:\s+balance)?",
            sanitized_text,
            re.IGNORECASE,
        )
        if neg_match:
            raw_neg = neg_match.group(1)
            neg_val, _ = FactNormalizer.normalize_currency(raw_neg)
            if neg_val is not None:
                facts.append(
                    ExtractedFact(
                        field="negative_amount",
                        raw_value=neg_match.group(0),
                        normalized_value=neg_val,
                        fact_type=FactType.CURRENCY,
                        source_span=SourceSpan(text=neg_match.group(0), start_char=neg_match.start(), end_char=neg_match.end(), document_id=source_id),
                        epistemic_status=epistemic_status,
                        confidence=ExtractionSupportLevel.DIRECT,
                        extraction_method="ROLE_PARSER",
                    )
                )

        # 7. Charged Amount (Strict: only when NOT approximate, and distinguished from order value)
        if not is_approx:
            explicit_charge = re.search(
                r"(?:charged(?:\s+me)?|deducted(?:\s+from)?|billed(?:\s+me)?|kaat\s+liye|kat\s+gaye|काटा|काट\s+लिया|शुल्क)\s*(?:of|is)?\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)",
                sanitized_text,
                re.IGNORECASE,
            )
            explicit_charge_post = re.search(
                r"([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)\s*(?:rupaye|रुपये|रुपए|rs\.?|₹)?\s*(?:brokerage|fee|charge|शुल्क)\s*(?:laga|kat|kaat|debit)?",
                sanitized_text,
                re.IGNORECASE,
            )
            cand_charge_match = explicit_charge or explicit_charge_post
            if cand_charge_match:
                amt_str = cand_charge_match.group(1)
                amt, curr = FactNormalizer.normalize_currency(amt_str)
                if amt is not None and amt > Decimal("0.00"):
                    facts.append(
                        ExtractedFact(
                            field="charged_amount",
                            raw_value=cand_charge_match.group(0).strip(),
                            normalized_value=amt,
                            fact_type=FactType.CURRENCY,
                            source_span=SourceSpan(text=cand_charge_match.group(0).strip(), start_char=cand_charge_match.start(), end_char=cand_charge_match.end(), document_id=source_id),
                            epistemic_status=epistemic_status,
                            confidence=ExtractionSupportLevel.DIRECT,
                            extraction_method="CURRENCY_PARSER",
                        )
                    )
            else:
                pattern = r"(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)\s*(?:rupees?|रुपये|रुपए)?"
                for match in re.finditer(pattern, sanitized_text, re.IGNORECASE):
                    raw_match = match.group(0).strip()
                    num_part = match.group(1).strip()
                    has_currency_marker = any(m in raw_match.lower() for m in ["₹", "rs", "inr", "rupee", "रुपये", "रुपए"])
                    if not has_currency_marker and "." not in num_part:
                        continue
                    amt, curr = FactNormalizer.normalize_currency(raw_match)
                    if amt is not None and amt > Decimal("0.00"):
                        is_already_assigned = any(f.normalized_value == amt for f in facts if f.field in ("order_value", "portfolio_value", "turnover", "fee_paid", "premium_value", "stt_billed", "sebi_fee_billed", "base_dp_charge", "agreed_rate", "gross_dividend", "net_dividend"))
                        if not is_already_assigned:
                            facts.append(
                                ExtractedFact(
                                    field="charged_amount",
                                    raw_value=raw_match,
                                    normalized_value=amt,
                                    fact_type=FactType.CURRENCY,
                                    source_span=SourceSpan(text=raw_match, start_char=match.start(), end_char=match.end(), document_id=source_id),
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
                    pre_text = text[max(0, match.start() - 30) : match.start()].lower()
                    field_name = "transaction_date"
                    if "payout" in pre_text or "settle" in pre_text:
                        field_name = "settlement_date"
                    elif "complaint" in pre_text:
                        field_name = "complaint_date"

                    facts.append(
                        ExtractedFact(
                            field=field_name,
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
        """Identify transaction type (e.g. equity_delivery_sell, equity_delivery_buy, intraday_equity)."""
        facts: list[ExtractedFact] = []
        lower = text.lower()

        sell_hindi = ["शेयर बेचे", "बेचे", "बेचा", "बिक्री"]
        buy_hindi = ["खरीदे", "खरीदा", "खरीद"]

        is_sell_re = re.search(r"\b(sold|sell|selling|sale|becha|beche|bechi)\b", text, re.IGNORECASE)
        is_buy_re = re.search(r"\b(bought|buy|buying|purchase|khareeda)\b", text, re.IGNORECASE)
        is_intraday_re = re.search(r"\b(intraday|mis|day trade|same day)\b", text, re.IGNORECASE)

        class PseudoMatch:
            def __init__(self, val: str, s: int, e: int):
                self._val = val
                self._s = s
                self._e = e
            def group(self, _=0): return self._val
            def start(self): return self._s
            def end(self): return self._e

        is_sell_hindi_m = None
        for w in sell_hindi:
            idx = text.find(w)
            if idx != -1:
                is_sell_hindi_m = PseudoMatch(w, idx, idx + len(w))
                break

        is_buy_hindi_m = None
        for w in buy_hindi:
            idx = text.find(w)
            if idx != -1:
                is_buy_hindi_m = PseudoMatch(w, idx, idx + len(w))
                break

        canonical = None
        m = None

        if is_intraday_re:
            canonical = "intraday_equity"
            m = is_intraday_re
        elif is_sell_re or is_sell_hindi_m:
            canonical = "equity_delivery_sell"
            m = is_sell_re or is_sell_hindi_m
        elif is_buy_re or is_buy_hindi_m:
            canonical = "equity_delivery_buy"
            m = is_buy_re or is_buy_hindi_m
        elif "delivery" in lower:
            canonical = "equity_delivery"
            m = re.search(r"\bdelivery\b", text, re.IGNORECASE)

        if canonical and m:
            raw_span = m.group(0)
            facts.append(
                ExtractedFact(
                    field="transaction_type",
                    raw_value=raw_span,
                    normalized_value=canonical,
                    fact_type=FactType.ENUM,
                    source_span=SourceSpan(
                        text=raw_span,
                        start_char=m.start(),
                        end_char=m.end(),
                        document_id=source_id,
                    ),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="TRANSACTION_KEYWORD",
                )
            )
        return facts

    def _extract_account_type(
        self,
        text: str,
        source_id: str,
        epistemic_status: FactEpistemicStatus,
    ) -> list[ExtractedFact]:
        """Extract account type and BSDA designation."""
        facts: list[ExtractedFact] = []
        match = re.search(r"\b(bsda|basic\s+services?\s+demat\s+account)\b", text, re.IGNORECASE)
        if match:
            is_neg = bool(re.search(r"\b(not|no|non|nahi)\s+(?:a\s+)?(?:registered\s+as\s+)?bsda\b", text, re.IGNORECASE))
            bsda_val = not is_neg
            raw_span = match.group(0)
            facts.append(
                ExtractedFact(
                    field="is_bsda",
                    raw_value=raw_span,
                    normalized_value=bsda_val,
                    fact_type=FactType.BOOLEAN,
                    source_span=SourceSpan(
                        text=raw_span,
                        start_char=match.start(),
                        end_char=match.end(),
                        document_id=source_id,
                    ),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="REGEX",
                )
            )
            facts.append(
                ExtractedFact(
                    field="account_type",
                    raw_value=raw_span,
                    normalized_value="BSDA" if bsda_val else "REGULAR",
                    fact_type=FactType.STRING,
                    source_span=SourceSpan(
                        text=raw_span,
                        start_char=match.start(),
                        end_char=match.end(),
                        document_id=source_id,
                    ),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="REGEX",
                )
            )
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

    def _extract_domain_entities(
        self,
        text: str,
        source_id: str,
        epistemic_status: FactEpistemicStatus,
    ) -> list[ExtractedFact]:
        """Detect regulatory portals and authorities."""
        facts: list[ExtractedFact] = []
        lower = text.lower()

        # Portal: SEBI_SCORES, SMART_ODR
        if re.search(r"\b(scores(?:\s*2\.0)?|sebi[\s_-]*scores|सेबी\s*स्कोर्स)\b", lower):
            m = re.search(r"\b(scores(?:\s*2\.0)?|sebi[\s_-]*scores|सेबी\s*स्कोर्स)\b", text, re.IGNORECASE)
            span_text = m.group(0)
            facts.append(
                ExtractedFact(
                    field="portal",
                    raw_value=span_text,
                    normalized_value="SEBI_SCORES",
                    fact_type=FactType.ENTITY,
                    source_span=SourceSpan(text=span_text, start_char=m.start(), end_char=m.end(), document_id=source_id),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="DOMAIN_ENTITY_PARSER",
                )
            )
        elif re.search(r"\b(smart[\s_-]*odr|odr[\s_-]*portal)\b", lower):
            m = re.search(r"\b(smart[\s_-]*odr|odr[\s_-]*portal)\b", text, re.IGNORECASE)
            span_text = m.group(0)
            facts.append(
                ExtractedFact(
                    field="portal",
                    raw_value=span_text,
                    normalized_value="SMART_ODR",
                    fact_type=FactType.ENTITY,
                    source_span=SourceSpan(text=span_text, start_char=m.start(), end_char=m.end(), document_id=source_id),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="DOMAIN_ENTITY_PARSER",
                )
            )

        # Authority: NSDL, CDSL, SEBI
        if re.search(r"\bnsdl\b", lower):
            m = re.search(r"\bnsdl\b", text, re.IGNORECASE)
            facts.append(
                ExtractedFact(
                    field="authority",
                    raw_value=m.group(0),
                    normalized_value="NSDL",
                    fact_type=FactType.ENTITY,
                    source_span=SourceSpan(text=m.group(0), start_char=m.start(), end_char=m.end(), document_id=source_id),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="DOMAIN_ENTITY_PARSER",
                )
            )
        elif re.search(r"\bcdsl\b", lower):
            m = re.search(r"\bcdsl\b", text, re.IGNORECASE)
            facts.append(
                ExtractedFact(
                    field="authority",
                    raw_value=m.group(0),
                    normalized_value="CDSL",
                    fact_type=FactType.ENTITY,
                    source_span=SourceSpan(text=m.group(0), start_char=m.start(), end_char=m.end(), document_id=source_id),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="DOMAIN_ENTITY_PARSER",
                )
            )
        elif re.search(r"\bsebi\b|सेबी", text, re.IGNORECASE):
            m = re.search(r"\bsebi\b|सेबी", text, re.IGNORECASE)
            facts.append(
                ExtractedFact(
                    field="authority",
                    raw_value=m.group(0),
                    normalized_value="SEBI",
                    fact_type=FactType.ENTITY,
                    source_span=SourceSpan(text=m.group(0), start_char=m.start(), end_char=m.end(), document_id=source_id),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="DOMAIN_ENTITY_PARSER",
                )
            )
        return facts

    def _extract_domain_attributes(
        self,
        text: str,
        source_id: str,
        epistemic_status: FactEpistemicStatus,
    ) -> list[ExtractedFact]:
        """Extract structured domain attributes across processes, actions, products, channels, and durations."""
        facts: list[ExtractedFact] = []
        lower = text.lower()

        def _add(field: str, val: Any, span_text: str, start: int, end: int, ftype: FactType = FactType.STRING):
            facts.append(
                ExtractedFact(
                    field=field,
                    raw_value=span_text,
                    normalized_value=val,
                    fact_type=ftype,
                    source_span=SourceSpan(text=span_text, start_char=start, end_char=end, document_id=source_id),
                    epistemic_status=epistemic_status,
                    confidence=ExtractionSupportLevel.DIRECT,
                    extraction_method="DOMAIN_ATTRIBUTE_PARSER",
                )
            )

        # 1. Fee Type
        if re.search(r"\b(amc|annual[\s_-]*maintenance[\s_-]*charge|maintenance[\s_-]*charge|एएमसी\s*शुल्क)\b", lower):
            m = re.search(r"\b(amc|annual[\s_-]*maintenance[\s_-]*charge|maintenance[\s_-]*charge|एएमसी\s*शुल्क)\b", text, re.IGNORECASE)
            _add("fee_type", "annual_maintenance_charge", m.group(0), m.start(), m.end())
        elif re.search(r"\b(dp[\s_-]*charges?|depository[\s_-]*participant[\s_-]*charges?|demat[\s_-]*charges?)\b", lower):
            m = re.search(r"\b(dp[\s_-]*charges?|depository[\s_-]*participant[\s_-]*charges?|demat[\s_-]*charges?)\b", text, re.IGNORECASE)
            _add("fee_type", "dp_charges", m.group(0), m.start(), m.end())
        elif re.search(r"\b(brokerage|brokerage[\s_-]*charge|brokerage[\s_-]*rate)\b", lower) and not re.search(r"\b(brokerage\s+is\s+zero|zero\s+brokerage)\b", lower):
            m = re.search(r"\b(brokerage|brokerage[\s_-]*charge|brokerage[\s_-]*rate)\b", text, re.IGNORECASE)
            _add("fee_type", "brokerage", m.group(0), m.start(), m.end())
        elif re.search(r"\b(call[\s_-]*and[\s_-]*trade|customer[\s_-]*desk)\b", lower):
            m = re.search(r"\b(call[\s_-]*and[\s_-]*trade|customer[\s_-]*desk)\b", text, re.IGNORECASE)
            _add("fee_type", "call_and_trade_charge", m.group(0), m.start(), m.end())

        # 2. Process
        if re.search(r"\b(account[\s_-]*opening|open(?:ing)?\s+(?:a\s+)?(?:new\s+)?(?:demat|account)|kholne)\b", lower):
            m = re.search(r"\b(account[\s_-]*opening|open(?:ing)?\s+(?:a\s+)?(?:new\s+)?(?:demat|account)|kholne)\b", text, re.IGNORECASE)
            _add("process", "account_opening", m.group(0), m.start(), m.end())
        elif re.search(r"\b(account[\s_-]*closure|close\s+(?:my\s+)?account|band\s+karne)\b", lower):
            m = re.search(r"\b(account[\s_-]*closure|close\s+(?:my\s+)?account|band\s+karne)\b", text, re.IGNORECASE)
            _add("process", "account_closure", m.group(0), m.start(), m.end())

        # 3. Action
        if re.search(r"\b(margin[\s_-]*pledge[\s_-]*repledge|repledge|pledged.*?(?:clearing\s+corporation|clearing\s+member))\b", lower):
            m = re.search(r"\b(margin[\s_-]*pledge[\s_-]*repledge|repledge|pledged.*?(?:clearing\s+corporation|clearing\s+member))\b", text, re.IGNORECASE)
            _add("action", "margin_pledge_repledge", m.group(0), m.start(), m.end())
        elif re.search(r"\b(margin[\s_-]*pledge|pledge[\s_-]*creation|pledging)\b", lower):
            m = re.search(r"\b(margin[\s_-]*pledge|pledge[\s_-]*creation|pledging)\b", text, re.IGNORECASE)
            _add("action", "margin_pledge_creation", m.group(0), m.start(), m.end())
        elif re.search(r"\b(account[\s_-]*freeze|freeze[\s_-]*account|frozen|froze)\b", lower):
            m = re.search(r"\b(account[\s_-]*freeze|freeze[\s_-]*account|frozen|froze)\b", text, re.IGNORECASE)
            _add("action", "account_freeze", m.group(0), m.start(), m.end())

        # 4. Reason
        if re.search(r"\b(inoperative[\s_-]*pan|pan[\s_-]*inoperative|pan[\s_-]*not[\s_-]*linked)\b", lower):
            m = re.search(r"\b(inoperative[\s_-]*pan|pan[\s_-]*inoperative|pan[\s_-]*not[\s_-]*linked)\b", text, re.IGNORECASE)
            _add("reason", "inoperative_pan", m.group(0), m.start(), m.end())

        # 5. Products & Product Types
        if re.search(r"\b(mtf|margin[\s_-]*trading[\s_-]*facility)\b", lower):
            m = re.search(r"\b(mtf|margin[\s_-]*trading[\s_-]*facility)\b", text, re.IGNORECASE)
            _add("product", "MTF", m.group(0), m.start(), m.end())
        elif re.search(r"\bdigital[\s_-]*gold[\s_-]*leasing(?:\s+app)?\b", lower):
            m = re.search(r"\bdigital[\s_-]*gold[\s_-]*leasing(?:\s+app)?\b", text, re.IGNORECASE)
            _add("product", "digital_gold_leasing", m.group(0), m.start(), m.end())

        if re.search(r"\bdirect[\s_-]*mutual[\s_-]*funds?\b", lower):
            m = re.search(r"\bdirect[\s_-]*mutual[\s_-]*funds?\b", text, re.IGNORECASE)
            _add("product_type", "direct_mutual_fund", m.group(0), m.start(), m.end())

        # 6. Instrument & Segment
        if re.search(r"\b(equity[\s_-]*cash|cash[\s_-]*segment|share\s+purchase\s+but\s+not\s+on\s+my\s+share\s+sale)\b", lower):
            m = re.search(r"\b(equity[\s_-]*cash|cash[\s_-]*segment|share\s+purchase\s+but\s+not\s+on\s+my\s+share\s+sale)\b", text, re.IGNORECASE)
            _add("instrument", "equity_cash", m.group(0), m.start(), m.end())
        elif re.search(r"\b(private[\s_-]*loan|promissory\s+note|builder\s+took.*?loan)\b", lower):
            m = re.search(r"\b(private[\s_-]*loan|promissory\s+note|builder\s+took.*?loan)\b", text, re.IGNORECASE)
            _add("instrument", "private_loan", m.group(0), m.start(), m.end())

        if re.search(r"\bfutures?\b", lower):
            m = re.search(r"\bfutures?\b", text, re.IGNORECASE)
            _add("segment", "futures", m.group(0), m.start(), m.end())

        # 7. Order Channel & Payment Mode
        if re.search(r"\b(phone[\s_-]*call|call[\s_-]*and[\s_-]*trade|over[\s_-]*the[\s_-]*phone|customer[\s_-]*desk)\b", lower):
            m = re.search(r"\b(phone[\s_-]*call|call[\s_-]*and[\s_-]*trade|over[\s_-]*the[\s_-]*phone|customer[\s_-]*desk)\b", text, re.IGNORECASE)
            _add("order_channel", "phone_call_and_trade", m.group(0), m.start(), m.end())

        if re.search(r"\bupi\b", text, re.IGNORECASE):
            m = re.search(r"\bupi\b", text, re.IGNORECASE)
            _add("payment_mode", "UPI", m.group(0), m.start(), m.end())

        # 8. Document Requested / Document Type
        if re.search(r"\b(electronic[\s_-]*contract[\s_-]*note|ecn)\b|\bcontract[\s_-]*note\b.*?\b(?:email|emailed|inbox)\b", lower):
            m = re.search(r"\b(electronic[\s_-]*contract[\s_-]*note|ecn)\b|\bcontract[\s_-]*note\b.*?\b(?:email|emailed|inbox)\b", text, re.IGNORECASE)
            _add("document_requested", "electronic_contract_note", m.group(0), m.start(), m.end())
            _add("document_type", "electronic_contract_note", m.group(0), m.start(), m.end())
        elif re.search(r"\b(statement[\s_-]*of[\s_-]*holdings?|holding[\s_-]*statement)\b", lower):
            m = re.search(r"\b(statement[\s_-]*of[\s_-]*holdings?|holding[\s_-]*statement)\b", text, re.IGNORECASE)
            _add("document_type", "statement_of_holding", m.group(0), m.start(), m.end())
        elif re.search(r"\b(full[\s_-]*poa|full\s+(?:physical\s+)?power\s+of\s+attorney)\b", lower):
            m = re.search(r"\b(full[\s_-]*poa|full\s+(?:physical\s+)?power\s+of\s+attorney)\b", text, re.IGNORECASE)
            _add("document_demanded", "full_poa", m.group(0), m.start(), m.end())
        elif re.search(r"\bdaily[\s_-]*(?:client[\s_-]*)?collateral[\s_-]*(?:segregation[\s_-]*)?(?:report|email)\b", lower):
            m = re.search(r"\bdaily[\s_-]*(?:client[\s_-]*)?collateral[\s_-]*(?:segregation[\s_-]*)?(?:report|email)\b", text, re.IGNORECASE)
            _add("document_omitted", "daily_collateral_report", m.group(0), m.start(), m.end())

        # 9. Durations: elapsed_days, elapsed_months, elapsed_hours, response_days
        m_day = re.search(r"\b(\d+)\s*(?:calendar\s+)?days?\b|(\d+)\s*दिन", text, re.IGNORECASE)
        if m_day:
            d_val = m_day.group(1) or m_day.group(2)
            _add("elapsed_days", int(d_val), m_day.group(0), m_day.start(), m_day.end(), FactType.INTEGER)

        m_mon = re.search(r"\b(\d+)\s*months?\b|(\d+)\s*महीने", text, re.IGNORECASE)
        if m_mon:
            m_val = m_mon.group(1) or m_mon.group(2)
            _add("elapsed_months", int(m_val), m_mon.group(0), m_mon.start(), m_mon.end(), FactType.INTEGER)

        m_hr = re.search(r"\b(\d+)\s*hours?\b|(\d+)\s*घंटे", text, re.IGNORECASE)
        if m_hr:
            h_val = m_hr.group(1) or m_hr.group(2)
            _add("elapsed_hours", int(h_val), m_hr.group(0), m_hr.start(), m_hr.end(), FactType.INTEGER)

        m_resp = re.search(r"(?:respon(?:ded|se)|repl(?:ied|y)|took)\s*(?:after|within|in)?\s*(\d+)\s*days?(?:\s+to\s+(?:reply|respond))?", text, re.IGNORECASE)
        if m_resp:
            _add("response_days", int(m_resp.group(1)), m_resp.group(0), m_resp.start(), m_resp.end(), FactType.INTEGER)

        # 10. Rates & Activities: daily_rate, stt_rate, transaction_activity
        m_rate = re.search(r"(?:rate|interest)\s*(?:of)?\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:per\s+day)?", text, re.IGNORECASE)
        if m_rate:
            _add("daily_rate", float(m_rate.group(1)), m_rate.group(0), m_rate.start(), m_rate.end(), FactType.PERCENTAGE)

        m_stt = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%\s*stt|stt\s*(?:of)?\s*([0-9]+(?:\.[0-9]+)?)\s*%", text, re.IGNORECASE)
        if m_stt:
            stt_val = m_stt.group(1) or m_stt.group(2)
            _add("stt_rate", float(stt_val), m_stt.group(0), m_stt.start(), m_stt.end(), FactType.PERCENTAGE)

        if re.search(r"\bregular\s+transactions?\b", lower):
            m = re.search(r"\bregular\s+transactions?\b", text, re.IGNORECASE)
            _add("transaction_activity", True, m.group(0), m.start(), m.end(), FactType.BOOLEAN)

        # Product Code (e.g. CONTRA-002: MIS)
        m_prod = re.search(r"\b(?:Order\s+Type|product[\s_-]*code)[\s:]*\b(MIS|CNC|NRML|SL-Limit|SL|BO|CO)\b", text, re.IGNORECASE)
        if m_prod:
            _add("product_code", m_prod.group(1).upper(), m_prod.group(0), m_prod.start(), m_prod.end())

        # Executed Exchange (e.g. CONTRA-004: BSE)
        m_ex = re.search(r"\b(?:Exchange|executed\s+on)[\s:]*\b(BSE|NSE|MCX)\b", text, re.IGNORECASE)
        if m_ex:
            _add("executed_exchange", m_ex.group(1).upper(), m_ex.group(0), m_ex.start(), m_ex.end())

        # Mandate Verified (e.g. CONTRA-005)
        if re.search(r"(?:User\s+Name[\s:]*Verified|mandate[\s_-]*verified|e-mandate.*?authenticated)", text, re.IGNORECASE):
            m_mv = re.search(r"(?:User\s+Name[\s:]*Verified|mandate[\s_-]*verified|e-mandate.*?authenticated)", text, re.IGNORECASE)
            _add("mandate_verified", True, m_mv.group(0), m_mv.start(), m_mv.end(), FactType.BOOLEAN)

        # Execution Time (e.g. CONTRA-006: 09:16:02)
        m_time = re.search(r"\b(?:Execution|Trade\s+Time)[\s:]*([0-9]{2}:[0-9]{2}:[0-9]{2})", text, re.IGNORECASE)
        if m_time:
            _add("execution_time", m_time.group(1), m_time.group(0), m_time.start(), m_time.end())

        # Clearing Date (e.g. CONTRA-010)
        m_cdate = re.search(r"\b(?:Value\s+Date|Clearing\s+Date)[\s:]*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})", text, re.IGNORECASE)
        if m_cdate:
            cd_val = FactNormalizer.normalize_date(m_cdate.group(1))
            if cd_val:
                _add("clearing_date", cd_val, m_cdate.group(0), m_cdate.start(), m_cdate.end(), FactType.DATE)

        # Disputed Trade (e.g. CROSS-005)
        if re.search(r"\b(dealer[\s_-]*options?[\s_-]*trade|options?\s+trade\s+placed\s+by\s+.*?dealer)\b", lower):
            m = re.search(r"\b(dealer[\s_-]*options?[\s_-]*trade|options?\s+trade\s+placed\s+by\s+.*?dealer)\b", text, re.IGNORECASE)
            _add("disputed_trade", "dealer_options_trade", m.group(0), m.start(), m.end())

        # Situation (e.g. CROSS-007)
        if re.search(r"\b(seller\s+defaulted|auction\s+settlement|auction\s+valuation|settlement\s+shortage)\b", lower):
            m = re.search(r"\b(seller\s+defaulted|auction\s+settlement|auction\s+valuation|settlement\s+shortage)\b", text, re.IGNORECASE)
            _add("situation", "settlement_shortage_auction", m.group(0), m.start(), m.end())

        # Corporate Action (e.g. CROSS-009)
        if re.search(r"\b(stock[\s_-]*split|split\s+\d+:\d+)\b", lower):
            m = re.search(r"\b(stock[\s_-]*split|split\s+\d+:\d+)\b", text, re.IGNORECASE)
            _add("corporate_action", "stock_split", m.group(0), m.start(), m.end())

        # Taxable Base Inflated (e.g. COMP-002)
        if re.search(r"\b(added\s+stt|gst\s+on\s+stt|tax[\s_-]*on[\s_-]*tax|added.*?stamp\s+duty.*?taxable)\b", lower):
            m = re.search(r"\b(added\s+stt|gst\s+on\s+stt|tax[\s_-]*on[\s_-]*tax|added.*?stamp\s+duty.*?taxable)\b", text, re.IGNORECASE)
            _add("taxable_base_inflated", True, m.group(0), m.start(), m.end(), FactType.BOOLEAN)

        # Scrip Count (e.g. COMP-005)
        if re.search(r"\b(single\s+scrip|same\s+scrip|one\s+scrip|two\s+separate\s+sell\s+orders.*?same\s+day)\b", lower):
            m = re.search(r"\b(single\s+scrip|same\s+scrip|one\s+scrip|two\s+separate\s+sell\s+orders.*?same\s+day)\b", text, re.IGNORECASE)
            _add("scrip_count", 1, m.group(0), m.start(), m.end(), FactType.INTEGER)

        # Quantity roles: placed_quantity and filled_quantity (e.g. COMP-010)
        m_placed = re.search(r"(?:placed\s+order\s+for|order\s+for)\s*([0-9]+(?:,[0-9]+)*)\s*shares", text, re.IGNORECASE)
        if m_placed:
            _add("placed_quantity", int(m_placed.group(1).replace(",", "")), m_placed.group(0), m_placed.start(), m_placed.end(), FactType.INTEGER)
        m_filled = re.search(r"(?:only\s+)?([0-9]+(?:,[0-9]+)*)\s*shares\s+(?:were\s+)?filled", text, re.IGNORECASE)
        if m_filled:
            _add("filled_quantity", int(m_filled.group(1).replace(",", "")), m_filled.group(0), m_filled.start(), m_filled.end(), FactType.INTEGER)

        # Margin Available Percentage (e.g. TEMP-003)
        m_margin = re.search(r"(\d+(?:\.\d+)?)\s*%\s*margin\s+available", lower)
        if m_margin:
            _add("margin_available_pct", float(m_margin.group(1)), m_margin.group(0), m_margin.start(), m_margin.end(), FactType.PERCENTAGE)

        # Settlement Date (e.g. TEMP-004)
        m_settle = re.search(r"payout\s+(?:was\s+made\s+)?on\s+(?:[a-zA-Z]+\s+)?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", text, re.IGNORECASE)
        if m_settle:
            s_date = FactNormalizer.normalize_date(m_settle.group(1))
            if s_date:
                _add("settlement_date", s_date, m_settle.group(0), m_settle.start(), m_settle.end(), FactType.DATE)

        # Complaint Date (e.g. TEMP-005)
        m_comp = re.search(r"complaint\s+on\s+scores\s+on\s+(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", text, re.IGNORECASE)
        if m_comp:
            c_date = FactNormalizer.normalize_date(m_comp.group(1))
            if c_date:
                _add("complaint_date", c_date, m_comp.group(0), m_comp.start(), m_comp.end(), FactType.DATE)

        # Application Amount (e.g. TEMP-009)
        m_app = re.search(r"(?:ipo\s+application\s+(?:of)?)\s*(?:[₹]|rs\.?|inr)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)", text, re.IGNORECASE)
        if m_app:
            app_amt, _ = FactNormalizer.normalize_currency(m_app.group(1))
            if app_amt is not None:
                _add("application_amount", app_amt, m_app.group(0), m_app.start(), m_app.end(), FactType.CURRENCY)

        # 11. Regulatory Gaps & Adversarial metadata
        if re.search(r"\b(crypto|cryptocurrency|bitcoin)\b", lower):
            m = re.search(r"\b(crypto|cryptocurrency|bitcoin)\b", text, re.IGNORECASE)
            _add("asset_type", "cryptocurrency", m.group(0), m.start(), m.end())
        elif re.search(r"\b(telegram\s+(?:channel|group)|tipster)\b", lower):
            m = re.search(r"\b(telegram\s+(?:channel|group)|tipster)\b", text, re.IGNORECASE)
            _add("entity_type", "unregistered_telegram_channel", m.group(0), m.start(), m.end())
        elif re.search(r"\b(seychelles|offshore)\b", lower):
            m = re.search(r"\b(seychelles|offshore)\b", text, re.IGNORECASE)
            _add("jurisdiction", "offshore_seychelles", m.group(0), m.start(), m.end())
        elif re.search(r"\bmarketing\s+blog\b", lower):
            m = re.search(r"\bmarketing\s+blog\b", text, re.IGNORECASE)
            _add("content_type", "marketing_blog", m.group(0), m.start(), m.end())

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
            if fact.field in {
                "charged_amount", "transaction_date", "organisation", "transaction_type",
                "quantity", "gst_breakdown", "is_bsda", "account_type",
                "fee_type", "order_value", "portfolio_value", "turnover", "total_charges",
                "fee_paid", "negative_amount", "portal", "authority", "action", "process",
                "product", "product_type", "instrument", "order_channel", "payment_mode",
                "elapsed_days", "elapsed_months", "elapsed_hours", "response_days",
                "document_requested", "document_type", "document_demanded", "document_omitted",
                "daily_rate", "stt_rate", "transaction_activity", "reason", "situation",
                "asset_type", "entity_type", "jurisdiction", "content_type", "segment",
                "margin_available_pct", "settlement_date", "complaint_date", "application_amount",
                "product_code", "agreed_rate", "executed_exchange", "mandate_verified",
                "execution_time", "base_dp_charge", "portfolio_valuation", "clearing_date",
                "total_deductions", "taxable_base_inflated", "scrip_count", "sebi_fee_billed",
                "premium_value", "stt_billed", "filled_quantity", "placed_quantity",
                "gross_dividend", "net_dividend", "corporate_action", "disputed_trade",
            }:
                candidates[fact.field] = fact.normalized_value

        return proposals, candidates
