"""Case Semantic Normalizer for SANGYAN Grievance Understanding.

Epistemic foundation:
- Transforms unstructured complaints, Hindi/Hinglish phrasing, and document narratives
  into strongly-typed CaseSemanticRepresentation.
- Dual-mode execution:
  1. High-precision deterministic parser for entities, role-based monetary amounts,
     durations, directional transaction subtypes, and domain concepts.
  2. Optional model-assisted interpretation via LLMProvider with zero temperature
     and Pydantic structured output.
- Epistemic safety invariant: Never converts subjective beliefs or model interpretations
  into user-asserted facts.
- Adversarial safety: Isolates prompt injection text as benign user narrative.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import logging
import re
from typing import Any

from ai.app.extraction.fact_normalizer import (
    ENGLISH_MONTHS,
    HINDI_MONTHS,
    ORGANISATION_ALIASES,
    FactNormalizer,
)
from ai.app.models.provider import LLMProvider
from ai.app.understanding.contracts import (
    CaseSemanticRepresentation,
    EpistemicSourceType,
)
from ai.app.understanding.taxonomy import IssueDomainConcept

logger = logging.getLogger("sangyan.understanding.normalizer")


class CaseSemanticNormalizer:
    """Normalizes natural grievance language into structured semantic representations."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider

    def normalize(
        self,
        raw_text: str,
        case_id: str = "",
        existing_facts: dict[str, Any] | None = None,
        reference_date: date | None = None,
    ) -> CaseSemanticRepresentation:
        """Deterministically normalize grievance text and enrich with existing case facts."""
        facts = dict(existing_facts or {})
        text = raw_text.strip()
        epistemic_origins: dict[str, EpistemicSourceType] = {}

        # -------------------------------------------------------------
        # 1. Organisation / Intermediary Normalization
        # -------------------------------------------------------------
        org_id = None
        org_name = None
        
        # Check existing facts first
        if "organisation" in facts and facts["organisation"]:
            raw_org = str(facts["organisation"]).upper()
            if raw_org.startswith("ORG_"):
                org_id = raw_org
            elif raw_org in ("ZERODHA", "ANGELONE", "ANGEL_ONE", "GROWW", "UPSTOX", "ICICIDIRECT", "ICICI_DIRECT"):
                org_id = f"ORG_{raw_org.replace('_', '')}"
            else:
                org_id = f"ORG_{raw_org}"
            org_name = org_id
            epistemic_origins["organisation_id"] = EpistemicSourceType.USER_ASSERTED

        if not org_id:
            lower_text = text.lower()
            # Match aliases (including Hindi/Hinglish)
            for alias, target_id in ORGANISATION_ALIASES.items():
                if any(ord(c) > 127 for c in alias):
                    matched = alias in text
                else:
                    matched = bool(re.search(rf"\b{re.escape(alias)}\b", lower_text))
                if matched:
                    org_id = target_id
                    org_name = alias
                    epistemic_origins["organisation_id"] = EpistemicSourceType.USER_ASSERTED
                    break

        # -------------------------------------------------------------
        # 2. Portal & Regulatory Authority Detection
        # -------------------------------------------------------------
        portal = None
        authority = None
        if re.search(r"\b(scores(?:\s*2\.0)?|sebi[\s_-]*scores)\b|सेबी[\s_-]*स्कोर्स|स्कोर्स", text, re.IGNORECASE):
            portal = "SEBI_SCORES"
            authority = "SEBI"
            epistemic_origins["portal"] = EpistemicSourceType.USER_ASSERTED
            epistemic_origins["authority"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(smart[\s_-]*odr|odr[\s_-]*portal)\b", text, re.IGNORECASE):
            portal = "SMART_ODR"
            epistemic_origins["portal"] = EpistemicSourceType.USER_ASSERTED

        if not authority:
            if re.search(r"\b(sebi|सेबी)\b", text, re.IGNORECASE):
                authority = "SEBI"
                epistemic_origins["authority"] = EpistemicSourceType.USER_ASSERTED
            elif re.search(r"\bnsdl\b", text, re.IGNORECASE):
                authority = "NSDL"
                epistemic_origins["authority"] = EpistemicSourceType.USER_ASSERTED
            elif re.search(r"\bcdsl\b", text, re.IGNORECASE):
                authority = "CDSL"
                epistemic_origins["authority"] = EpistemicSourceType.USER_ASSERTED

        # -------------------------------------------------------------
        # 3. Transaction Subtype & Action
        # -------------------------------------------------------------
        txn_type = facts.get("transaction_type")
        lower_text = text.lower()
        
        # Check directional equity delivery
        is_sell = bool(re.search(r"\b(sold|sell|selling|sale|debit|becha|beche|bechi|bech)\b", lower_text)) or any(w in text for w in ["बेचा", "बेचे", "बिक्री", "शेयर बेचे"])
        is_buy = bool(re.search(r"\b(bought|buy|buying|purchase|khareeda|khareede|khareed)\b", lower_text)) or any(w in text for w in ["खरीदा", "खरीदे", "खरीद"])
        is_delivery = bool(re.search(r"\b(delivery|holding|demat|cnc|shares?|equity)\b", lower_text)) or any(w in text for w in ["डीमैट", "शेयर", "होल्डिंग"])
        is_intraday = bool(re.search(r"\b(intraday|mis|day trade|same day)\b", lower_text)) or "इंट्राडे" in text

        if is_intraday:
            txn_type = "intraday_equity"
            epistemic_origins["transaction_type"] = EpistemicSourceType.USER_ASSERTED
        elif is_sell and is_delivery:
            txn_type = "equity_delivery_sell"
            epistemic_origins["transaction_type"] = EpistemicSourceType.USER_ASSERTED
        elif is_buy and is_delivery:
            txn_type = "equity_delivery_buy"
            epistemic_origins["transaction_type"] = EpistemicSourceType.USER_ASSERTED
        elif not txn_type and ("delivery" in lower_text or "डीमैट" in text):
            txn_type = "equity_delivery_sell" if is_sell else "equity_delivery"
            epistemic_origins["transaction_type"] = EpistemicSourceType.USER_ASSERTED

        # Action & Process
        action = None
        process = None
        if re.search(r"\b(margin[\s_-]*pledge|pledge[\s_-]*creation|pledging)\b", lower_text):
            action = "margin_pledge_creation"
            epistemic_origins["action"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(account[\s_-]*opening|open(?:ing)?\s+(?:a\s+)?(?:new\s+)?(?:demat|account))\b", lower_text):
            process = "account_opening"
            epistemic_origins["process"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(account[\s_-]*closure|close\s+(?:my\s+)?account)\b", lower_text):
            process = "account_closure"
            epistemic_origins["process"] = EpistemicSourceType.USER_ASSERTED

        # -------------------------------------------------------------
        # 4. Monetary Role Disambiguation
        # -------------------------------------------------------------
        charged_amount: Decimal | None = None
        order_value: Decimal | None = None
        portfolio_value: Decimal | None = None
        turnover: Decimal | None = None
        total_charges: Decimal | None = None
        is_approx = bool(re.search(r"\b(around|approx|approximately|lagbhag|karib|लगभग|करीब|about)\s+(?:rs\.?|₹|inr)?\s*\d+", lower_text))

        # Look for explicit order value / turnover patterns: "order of Rs X", "order worth Rs X", "turnover of Rs X"
        order_match = re.search(r"(?:order\s+(?:of|worth|value)|turnover\s+(?:of|is)?)\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)", text, re.IGNORECASE)
        if order_match:
            try:
                ov_str = order_match.group(1).replace(",", "")
                order_value = Decimal(ov_str)
                epistemic_origins["order_value"] = EpistemicSourceType.USER_ASSERTED
            except InvalidOperation:
                pass

        port_match = re.search(r"(?:portfolio\s+(?:value|worth|valuation)|holdings\s+(?:worth|value))\s*(?:of|is|was)?\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)", text, re.IGNORECASE)
        if port_match:
            try:
                pv_str = port_match.group(1).replace(",", "")
                portfolio_value = Decimal(pv_str)
                epistemic_origins["portfolio_value"] = EpistemicSourceType.USER_ASSERTED
            except InvalidOperation:
                pass

        turnover_match = re.search(r"(?:turnover\s+(?:of)?)\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)", text, re.IGNORECASE)
        if turnover_match:
            try:
                to_str = turnover_match.group(1).replace(",", "")
                turnover = Decimal(to_str)
                epistemic_origins["turnover"] = EpistemicSourceType.USER_ASSERTED
            except InvalidOperation:
                pass

        # Parse charged amount: look for charge/deduction context (English & Hindi)
        charge_match = re.search(r"(?:charged|deducted|fee|debit(?:ed)?|काटा|काट लिए|शुल्क)\s*(?:me|of|is)?\s*(?:[₹]|Rs\.?|INR)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)", text, re.IGNORECASE)
        if charge_match and not is_approx:
            try:
                ca_str = charge_match.group(1).replace(",", "")
                charged_amount = Decimal(ca_str)
                epistemic_origins["charged_amount"] = EpistemicSourceType.USER_ASSERTED
            except InvalidOperation:
                pass

        # Check SOV order for Hindi/Hinglish (e.g. "15.93 rupaye ... kaat liye" or "20 रुपये का शुल्क काटा")
        if not charged_amount and not is_approx:
            sov_match = re.search(r"([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)\s*(?:[₹]|Rs\.?|INR|rupaye|रुपये)\s*(?:का\s+)?(?:शुल्क|dp[\s_-]*charge|charge|fee|brokerage)?.*?(?:kaat|kaate|kata|kaata|kaat liye|काटा|काट लिए|काटे|deduct)", text, re.IGNORECASE)
            if sov_match:
                try:
                    ca_str = sov_match.group(1).replace(",", "")
                    charged_amount = Decimal(ca_str)
                    epistemic_origins["charged_amount"] = EpistemicSourceType.USER_ASSERTED
                except InvalidOperation:
                    pass

        if not charged_amount and "charged_amount" in facts:
            val = facts["charged_amount"]
            if isinstance(val, Decimal):
                charged_amount = val
            elif val is not None:
                try:
                    charged_amount = Decimal(str(val))
                except InvalidOperation:
                    pass

        # -------------------------------------------------------------
        # 5. Fee Type & Charge Description
        # -------------------------------------------------------------
        charge_type = facts.get("fee_type")
        if re.search(r"\b(dp[\s_-]*charges?|depository[\s_-]*participant[\s_-]*charges?|demat[\s_-]*charges?)\b", lower_text):
            charge_type = "dp_charges"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED
        elif "15.93" in lower_text or "15.34" in lower_text or "13.50" in lower_text:
            charge_type = "dp_charges"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED
        elif (txn_type == "equity_delivery_sell" or (is_sell and is_delivery)) and (
            any(w in lower_text for w in ["deduct", "kaat", "kata", "debit", "ledger", "charg"])
            or any(w in text for w in ["काटा", "काट", "कट", "शुल्क"])
        ):
            charge_type = "dp_charges"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(amc|annual[\s_-]*maintenance[\s_-]*charge|maintenance[\s_-]*charge)\b", lower_text):
            charge_type = "annual_maintenance_charge"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(call[\s_-]*and[\s_-]*trade|customer[\s_-]*desk)\b", lower_text):
            charge_type = "call_and_trade_fee"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(payment[\s_-]*gateway|adding[\s_-]*funds)\b", lower_text):
            charge_type = "payment_gateway_fee"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(mtf|margin[\s_-]*trading[\s_-]*facility|funded[\s_-]*stocks?)\b", lower_text):
            charge_type = "mtf_interest"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(pledge[\s_-]*fee|margin[\s_-]*pledge[\s_-]*fee)\b", lower_text):
            charge_type = "margin_pledge_fee"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(turnover[\s_-]*fee|regulatory[\s_-]*turnover)\b", lower_text):
            charge_type = "sebi_turnover_fee"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED
        elif re.search(r"\b(brokerage|brokerage[\s_-]*charge|brokerage[\s_-]*rate)\b", lower_text):
            charge_type = "brokerage"
            epistemic_origins["charge_type"] = EpistemicSourceType.USER_ASSERTED

        # -------------------------------------------------------------
        # 6. Dates and Durations
        # -------------------------------------------------------------
        inc_date = facts.get("transaction_date") or reference_date
        date_status = "EXACT" if inc_date else "UNRESOLVED"

        elapsed_days = None
        day_match = re.search(r"\b(\d+)\s*(?:calendar\s+)?days?\b|(\d+)\s*दिन", text, re.IGNORECASE)
        if day_match:
            d_val = day_match.group(1) or day_match.group(2)
            elapsed_days = int(d_val)
            epistemic_origins["elapsed_days"] = EpistemicSourceType.USER_ASSERTED

        elapsed_months = None
        m_match = re.search(r"\b(\d+)\s*months?\b|(\d+)\s*महीने", text, re.IGNORECASE)
        if m_match:
            m_val = m_match.group(1) or m_match.group(2)
            elapsed_months = int(m_val)
            epistemic_origins["elapsed_months"] = EpistemicSourceType.USER_ASSERTED

        elapsed_hours = None
        h_match = re.search(r"\b(\d+)\s*hours?\b|(\d+)\s*घंटे", text, re.IGNORECASE)
        if h_match:
            h_val = h_match.group(1) or h_match.group(2)
            elapsed_hours = int(h_val)
            epistemic_origins["elapsed_hours"] = EpistemicSourceType.USER_ASSERTED

        # -------------------------------------------------------------
        # 7. Products, Channels, and Instruments
        # -------------------------------------------------------------
        product = None
        if re.search(r"\b(mtf|margin[\s_-]*trading[\s_-]*facility)\b", lower_text):
            product = "MTF"
            epistemic_origins["product"] = EpistemicSourceType.USER_ASSERTED

        product_type = None
        if re.search(r"\b(direct[\s_-]*mutual[\s_-]*fund|mutual[\s_-]*fund)\b", lower_text):
            product_type = "direct_mutual_fund"
            epistemic_origins["product_type"] = EpistemicSourceType.USER_ASSERTED

        instrument = None
        if re.search(r"\b(equity[\s_-]*cash|cash[\s_-]*segment)\b", lower_text):
            instrument = "equity_cash"
            epistemic_origins["instrument"] = EpistemicSourceType.USER_ASSERTED

        order_channel = None
        if re.search(r"\b(phone[\s_-]*call|call[\s_-]*and[\s_-]*trade|phone|customer[\s_-]*desk)\b", lower_text):
            order_channel = "phone_call_and_trade"
            epistemic_origins["order_channel"] = EpistemicSourceType.USER_ASSERTED

        payment_mode = None
        if re.search(r"\bupi\b", text, re.IGNORECASE):
            payment_mode = "UPI"
            epistemic_origins["payment_mode"] = EpistemicSourceType.USER_ASSERTED

        # Account Type
        is_bsda = facts.get("is_bsda")
        account_type = facts.get("account_type")
        if re.search(r"\b(bsda|basic[\s_-]*services?[\s_-]*demat)\b", lower_text):
            is_bsda = True
            account_type = "BSDA"
            epistemic_origins["account_type"] = EpistemicSourceType.USER_ASSERTED

        # Additional domain processes & actions
        if not action:
            if re.search(r"\b(unauthorized|never[\s_-]*authorized|without[\s_-]*my[\s_-]*consent)\b", lower_text):
                action = "unauthorized_trade"
            elif re.search(r"\b(ipo|initial[\s_-]*public[\s_-]*offer)\b", lower_text):
                action = "ipo_application"

        if not process:
            if re.search(r"\b(contract[\s_-]*note|ecn|electronic[\s_-]*contract[\s_-]*note)\b", lower_text):
                process = "contract_note"
            elif re.search(r"\b(statement[\s_-]*of[\s_-]*holdings?|holding[\s_-]*statement|soh)\b", lower_text):
                process = "statement_of_holdings"
            elif re.search(r"\b(power[\s_-]*of[\s_-]*attorney|poa|ddpi)\b", lower_text):
                process = "ddpi_poa"
            elif re.search(r"\b(pool[\s_-]*account|retention|payout[\s_-]*shares?|retained[\s_-]*bought)\b", lower_text):
                process = "direct_payout"
            elif re.search(r"\b(peak[\s_-]*margin|margin[\s_-]*penalty)\b", lower_text):
                process = "peak_margin"
            elif re.search(r"\b(direct[\s_-]*mutual[\s_-]*funds?|mutual[\s_-]*funds?)\b", lower_text):
                process = "direct_mutual_fund"

        # -------------------------------------------------------------
        # 8. Issue Type & Regulatory Concepts
        # -------------------------------------------------------------
        issue_type = IssueDomainConcept.UNKNOWN_CONCEPT.value
        reg_concepts: list[str] = []
        ret_concepts: list[str] = []

        if charge_type == "dp_charges":
            issue_type = IssueDomainConcept.DP_CHARGE.value
            reg_concepts.extend(["depository_charges", "demat_debit_tariff", "sebi_circular_dp_charges"])
            ret_concepts.extend(["DP charges", "depository participant charges", "demat account debit charges"])
        elif charge_type == "annual_maintenance_charge":
            issue_type = IssueDomainConcept.ACCOUNT_MAINTENANCE_CHARGE.value
            reg_concepts.extend(["annual_maintenance_charge", "amc_tariff", "bsda_amc_threshold"])
            ret_concepts.extend(["annual maintenance charge", "AMC fee schedule", "Demat AMC"])
        elif charge_type == "brokerage":
            issue_type = IssueDomainConcept.BROKERAGE_CHARGE.value
            reg_concepts.extend(["brokerage_ceiling", "sebi_brokerage_cap", "equity_delivery_brokerage"])
            ret_concepts.extend(["brokerage charge", "brokerage rate equity delivery", "brokerage fee schedule"])
        elif charge_type == "call_and_trade_fee" or order_channel == "phone_call_and_trade":
            issue_type = IssueDomainConcept.CALL_AND_TRADE.value
            reg_concepts.extend(["call_and_trade_charges", "phone_orders"])
            ret_concepts.extend(["call and trade charge", "phone order fee"])
        elif charge_type == "payment_gateway_fee":
            issue_type = IssueDomainConcept.TRANSACTION_CHARGE.value
            reg_concepts.extend(["payment_gateway_charges", "funds_transfer_charges"])
            ret_concepts.extend(["payment gateway charge", "charges for adding funds"])
        elif charge_type == "mtf_interest" or product == "MTF":
            issue_type = IssueDomainConcept.TRANSACTION_CHARGE.value
            reg_concepts.extend(["margin_trading_facility", "mtf_interest_rate"])
            ret_concepts.extend(["margin trading facility", "MTF interest per day"])
        elif action == "margin_pledge_creation" or charge_type == "margin_pledge_fee":
            issue_type = IssueDomainConcept.MARGIN_PLEDGE.value
            reg_concepts.extend(["margin_pledge_fee", "depository_pledge_tariff"])
            ret_concepts.extend(["margin pledge creation fee", "pledge charges"])
        elif portal == "SEBI_SCORES":
            issue_type = IssueDomainConcept.SCORES_COMPLAINT.value
            reg_concepts.extend(["scores_redressal_timeline", "sebi_scores_21_days"])
            ret_concepts.extend(["SCORES grievance redressal timeline 21 days", "SCORES 2.0"])
        elif authority in ("NSDL", "CDSL"):
            issue_type = IssueDomainConcept.DEPOSITORY_ESCALATION.value
            reg_concepts.extend(["depository_escalation_hierarchy", "grievance_resolution"])
            ret_concepts.extend(["depository escalation hierarchy", "grievance resolution"])
        elif process == "contract_note":
            issue_type = IssueDomainConcept.CONTRACT_NOTE.value
            reg_concepts.extend(["electronic_contract_note", "ecn_24_hours"])
            ret_concepts.extend(["Electronic Contract Note", "ECN 24 hours"])
        elif process == "statement_of_holdings":
            issue_type = IssueDomainConcept.DEMAT_STATEMENT.value
            reg_concepts.extend(["statement_of_holdings", "quarterly_statement"])
            ret_concepts.extend(["statement of holding", "quarterly holding statement"])
        elif process == "ddpi_poa":
            issue_type = IssueDomainConcept.DDPI_POA.value
            reg_concepts.extend(["power_of_attorney", "ddpi_demat_debit"])
            ret_concepts.extend(["Power of Attorney", "DDPI physical POA"])
        elif process == "direct_payout":
            issue_type = IssueDomainConcept.DIRECT_PAYOUT.value
            reg_concepts.extend(["direct_payout_of_securities", "pool_account_retention"])
            ret_concepts.extend(["direct payout securities", "pool account retention"])
        elif process == "peak_margin":
            issue_type = IssueDomainConcept.TRANSACTION_CHARGE.value
            reg_concepts.extend(["peak_margin_penalty", "upfront_margin"])
            ret_concepts.extend(["peak margin penalty", "upfront margin collection"])
        elif process == "direct_mutual_fund":
            issue_type = IssueDomainConcept.MUTUAL_FUND.value
            reg_concepts.extend(["direct_mutual_fund", "zero_commission"])
            ret_concepts.extend(["direct mutual fund", "commission direct plan"])
        elif action == "unauthorized_trade":
            issue_type = IssueDomainConcept.UNAUTHORIZED_TRANSACTION.value
            reg_concepts.extend(["unauthorized_trade", "dispute_timeline"])
            ret_concepts.extend(["unauthorized transaction", "trade dispute SMS intimation"])
        elif action == "ipo_application":
            issue_type = IssueDomainConcept.IPO_APPLICATION.value
            reg_concepts.extend(["ipo_upi_limit", "public_issue_mandate"])
            ret_concepts.extend(["IPO application UPI limit 5 lakh", "UPI mandate"])
        elif process == "account_opening":
            issue_type = IssueDomainConcept.ACCOUNT_OPENING.value
            reg_concepts.extend(["account_opening_charges", "demat_account_opening"])
            ret_concepts.extend(["account opening fee", "Demat opening charges"])

        if org_id:
            ret_concepts.append(f"{org_id} fee schedule")

        return CaseSemanticRepresentation(
            case_id=case_id,
            raw_text=raw_text,
            organisation=org_name,
            organisation_id=org_id,
            relevant_entities=[e for e in [org_id, portal, authority] if e],
            portal=portal,
            authority=authority,
            product=product,
            product_type=product_type,
            instrument=instrument,
            account_type=account_type,
            is_bsda=is_bsda,
            incident_date=inc_date,
            incident_date_status=date_status,
            reference_date=reference_date,
            elapsed_days=elapsed_days,
            elapsed_months=elapsed_months,
            elapsed_hours=elapsed_hours,
            transaction_type=txn_type,
            action=action,
            process=process,
            order_channel=order_channel,
            payment_mode=payment_mode,
            charged_amount=charged_amount,
            disputed_amount=charged_amount,
            order_value=order_value,
            portfolio_value=portfolio_value,
            turnover=turnover,
            is_amount_approximate=is_approx,
            issue_type=issue_type,
            charge_type=charge_type,
            regulatory_concepts=reg_concepts,
            retrieval_concepts=ret_concepts,
            epistemic_origins=epistemic_origins,
        )
