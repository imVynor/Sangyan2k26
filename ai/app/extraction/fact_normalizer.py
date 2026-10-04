"""Deterministic Fact Normalizer for SANGYAN Evidentiary Extraction.

Epistemic foundation:
- Financial values are coerced to Decimal with currency code 'INR'.
- Relative dates are resolved strictly against an explicit reference_date.
  Never silently assume current date when reference_date is absent.
- Entities are mapped deterministically to canonical IDs registered in the system.
  Never invent organisation identifiers.
- Multilingual aliases (English, Hindi, Hinglish) are mapped to canonical case facts.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import logging
import re
from typing import Any

logger = logging.getLogger("sangyan.extraction.fact_normalizer")

# Canonical Organisation Alias Mapping
ORGANISATION_ALIASES: dict[str, str] = {
    "zerodha": "ORG_ZERODHA",
    "zerodha broking": "ORG_ZERODHA",
    "zerodha broking limited": "ORG_ZERODHA",
    "zerodha broking ltd": "ORG_ZERODHA",
    "kite": "ORG_ZERODHA",
    "ज़ेरोधा": "ORG_ZERODHA",
    "angel one": "ORG_ANGELONE",
    "angel broking": "ORG_ANGELONE",
    "angelone": "ORG_ANGELONE",
    "एंजेल वन": "ORG_ANGELONE",
    "groww": "ORG_GROWW",
    "nextbillion": "ORG_GROWW",
    "nextbillion technology": "ORG_GROWW",
    "ग्रो": "ORG_GROWW",
    "upstox": "ORG_UPSTOX",
    "rksv": "ORG_UPSTOX",
    "rksv securities": "ORG_UPSTOX",
    "अपस्टॉक्स": "ORG_UPSTOX",
    "icici direct": "ORG_ICICIDIRECT",
    "icicidirect": "ORG_ICICIDIRECT",
    "icici securities": "ORG_ICICIDIRECT",
    "i-direct": "ORG_ICICIDIRECT",
    "आईसीआईसीआई डायरेक्ट": "ORG_ICICIDIRECT",
}

# Transaction Type Aliases
TRANSACTION_ALIASES: dict[str, str] = {
    "sell": "equity_delivery_sell",
    "sold": "equity_delivery_sell",
    "sale": "equity_delivery_sell",
    "selling": "equity_delivery_sell",
    "delivery sale": "equity_delivery_sell",
    "equity delivery sell": "equity_delivery_sell",
    "share sale": "equity_delivery_sell",
    "shares sold": "equity_delivery_sell",
    "sold shares": "equity_delivery_sell",
    "बेचा": "equity_delivery_sell",
    "बिक्री": "equity_delivery_sell",
    "शेयर बेचे": "equity_delivery_sell",
    "becha": "equity_delivery_sell",
    "sell kiya": "equity_delivery_sell",

    "buy": "equity_delivery_buy",
    "bought": "equity_delivery_buy",
    "purchase": "equity_delivery_buy",
    "buying": "equity_delivery_buy",
    "खरीदा": "equity_delivery_buy",
    "delivery buy": "equity_delivery_buy",
    "equity delivery buy": "equity_delivery_buy",

    "delivery": "equity_delivery",
    "equity delivery": "equity_delivery",

    "intraday": "intraday_equity",
    "mis": "intraday_equity",
    "square off": "intraday_equity",
    "day trade": "intraday_equity",
    "intraday buy": "intraday_equity",
    "intraday sell": "intraday_equity",

    "amc": "amc",
    "annual maintenance": "amc",
    "maintenance charge": "amc",
    "वार्षिक शुल्क": "amc",
    "pledge": "pledge",
    "unpledge": "pledge",
    "transmission": "transmission",
    "transfer": "demat_transfer",
    "off market": "off_market_transfer",
}

# Hindi Month Mapping
HINDI_MONTHS: dict[str, int] = {
    "जनवरी": 1, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6,
    "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "अक्टूबर": 10, "नवंबर": 11, "दिसंबर": 12,
}

ENGLISH_MONTHS: dict[str, int] = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12,
}


class FactNormalizer:
    """Normalizes raw extracted text spans into canonical, typed case facts."""

    ORGANISATION_ALIASES = ORGANISATION_ALIASES
    TRANSACTION_ALIASES = TRANSACTION_ALIASES

    @staticmethod
    def normalize_currency(text: str) -> tuple[Decimal | None, str]:
        """Extract and normalize monetary currency amount to Decimal (default INR).
        
        Returns:
            (Decimal amount, currency code)
        """
        if not text:
            return None, "INR"

        cleaned = text.strip()

        # Check Indian word denominations: e.g. 1 lakh, 2.5 lakh, 1 crore
        lakh_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|लाख)", cleaned, re.IGNORECASE)
        if lakh_match:
            try:
                amt = Decimal(lakh_match.group(1)) * Decimal("100000")
                return amt, "INR"
            except InvalidOperation:
                pass
        crore_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:crore|करोड़)", cleaned, re.IGNORECASE)
        if crore_match:
            try:
                amt = Decimal(crore_match.group(1)) * Decimal("10000000")
                return amt, "INR"
            except InvalidOperation:
                pass

        # Match currency symbols / prefixes
        # e.g. ₹15.93, Rs. 15.93, Rs 15.93, INR 15.93, 15.93 रुपये, 15.93 rupees
        pattern = r"(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,4})?)\s*(?:rupees?|रुपये|रुपए)?"
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            num_str = match.group(1).replace(",", "").strip()
            try:
                amt = Decimal(num_str)
                return amt, "INR"
            except InvalidOperation:
                pass

        return None, "INR"

    @staticmethod
    def normalize_percentage(text: str) -> Decimal | None:
        """Normalize percentage strings (e.g. '18%', '18 percent', '18% GST')."""
        if not text:
            return None

        pattern = r"([0-9]+(?:\.[0-9]+)?)\s*(?:%|percent|प्रतिशत)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return Decimal(match.group(1))
            except InvalidOperation:
                pass
        return None

    @staticmethod
    def normalize_date(text: str, reference_date: date | None = None) -> date | None:
        """Parse natural language dates, resolving relative dates strictly with reference_date."""
        if not text:
            return None

        cleaned = text.strip().lower()

        # 1. Relative dates (STRICT REQUIREMENT: must have reference_date)
        if cleaned in {"yesterday", "कल (बीता)", "beeta kal"}:
            if reference_date is None:
                logger.warning("Relative date 'yesterday' encountered without reference_date. Returning None.")
                return None
            return reference_date - timedelta(days=1)

        if cleaned in {"today", "आज", "aaj"}:
            if reference_date is None:
                logger.warning("Relative date 'today' encountered without reference_date. Returning None.")
                return None
            return reference_date

        # 2. Standard ISO & common date formats (e.g. 2026-09-12, 12/09/2026, 12-09-2026)
        iso_match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", cleaned)
        if iso_match:
            try:
                return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            except ValueError:
                pass

        dmy_match = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", cleaned)
        if dmy_match:
            try:
                return date(int(dmy_match.group(3)), int(dmy_match.group(2)), int(dmy_match.group(1)))
            except ValueError:
                pass

        # 3. Textual English format (e.g. "12 September 2026" or "September 12, 2026")
        text_dmy = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+),?\s+(\d{4})", cleaned)
        if text_dmy:
            day = int(text_dmy.group(1))
            month_name = text_dmy.group(2).lower()
            year = int(text_dmy.group(3))
            month = ENGLISH_MONTHS.get(month_name)
            if month:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass

        # 4. Textual Hindi format (e.g. "12 सितंबर 2026")
        for h_month, m_num in HINDI_MONTHS.items():
            if h_month in text:
                m = re.search(rf"(\d{{1,2}})\s*{h_month}\s*(\d{{4}})", text)
                if m:
                    try:
                        return date(int(m.group(2)), m_num, int(m.group(1)))
                    except ValueError:
                        pass

        return None

    @staticmethod
    def normalize_entity(text: str) -> str | None:
        """Map entity name/alias to canonical organisation ID registered in SANGYAN."""
        if not text:
            return None

        cleaned = text.strip().lower()
        # Direct lookup
        if cleaned in ORGANISATION_ALIASES:
            return ORGANISATION_ALIASES[cleaned]

        # Substring lookup
        for alias, org_id in ORGANISATION_ALIASES.items():
            if alias in cleaned:
                return org_id

        return None

    @staticmethod
    def normalize_transaction_type(text: str) -> str | None:
        """Map natural language transaction descriptions to canonical transaction types."""
        if not text:
            return None

        cleaned = text.strip().lower()
        if cleaned in TRANSACTION_ALIASES:
            return TRANSACTION_ALIASES[cleaned]

        for alias, canonical in TRANSACTION_ALIASES.items():
            if alias in cleaned:
                return canonical

        return None

    @staticmethod
    def detect_compound_gst(
        charged: Decimal,
        base_tariff: Decimal = Decimal("13.50"),
        gst_rate: Decimal = Decimal("0.18"),
    ) -> bool:
        """Check if charged amount matches base tariff + 18% GST (e.g. 13.50 * 1.18 = 15.93)."""
        expected_compound = (base_tariff * (Decimal("1.00") + gst_rate)).quantize(
            Decimal("0.01")
        )
        return charged == expected_compound
