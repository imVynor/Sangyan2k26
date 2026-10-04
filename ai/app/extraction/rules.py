"""Rule-based extraction patterns and classification heuristics for SANGYAN provisions.

Implements Sections 4 through 13:
- Conditions: Explicit preconditions ("Where the investor submits...", "Subject to...")
- Exceptions: Statutory exemptions ("except where...", "save and except...")
- Procedures: Ordered steps in grievance or administrative paths
- Timelines: Deadlines ("within 30 working days", "within 48 hours")
- Fees/Charges: Tariff schedules, brokerage fees, DP charges
- Definitions: Statutory definitions ("'Client' means...")
- Cross-References: External circular or regulation citations
- Classification: ProvisionType determination
"""

import re
from typing import Any

from ai.app.knowledge.provisions import (
    Condition,
    CrossReference,
    Definition,
    ExceptionClause,
    FeeOrCharge,
    ProcedureStep,
    ProvisionType,
    Timeline,
)
from ai.app.knowledge.source_classes import SourceClass


# --- Timelines ---
TIMELINE_RE = re.compile(
    r"\b(within|after|before|not\s+later\s+than|exceeding)\s+(\d+(?:\.\d+)?)\s*(working\s+days|business\s+days|calendar\s+days|days|hours|months|weeks|years)\b",
    re.IGNORECASE,
)

# --- Fees & Charges ---
FEE_RE = re.compile(
    r"(?:(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:Rs\.?|INR|₹))\s*(?:per\s+([a-zA-Z\s]+)|(?:[a-zA-Z\s]+))?",
    re.IGNORECASE,
)
PERCENTAGE_FEE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(?:of\s+([a-zA-Z\s]+)|(?:brokerage|turnover|charge))?",
    re.IGNORECASE,
)

# --- Definitions ---
DEFINITION_RE = re.compile(
    r'["“\']([^"”\']+)["”\']\s+(?:means|shall\s+mean|is\s+defined\s+as|refers\s+to)\s+([^.\n]+(?:\.[^.\n]+)?)',
    re.IGNORECASE,
)

# --- Cross-References ---
CROSS_REF_RE = re.compile(
    r"\b(?:Regulation|Clause|Circular|Section|Rule|Act|Notification)\s+(?:no\.?\s*)?([A-Za-z0-9/().-]+)",
    re.IGNORECASE,
)

# --- Conditions ---
CONDITION_PATTERNS = [
    re.compile(r"\b(where\s+the\s+[^,;]+|\bif\s+the\s+[^,;]+|subject\s+to\s+[^,;]+|provided\s+that\s+[^,;]+|upon\s+receipt\s+of\s+[^,;]+|in\s+the\s+event\s+of\s+[^,;]+)", re.IGNORECASE),
]

# --- Exceptions ---
EXCEPTION_PATTERNS = [
    re.compile(r"\b(except\s+(?:where|in|for|as)\s+[^.;]+|save\s+and\s+except\s+[^.;]+|other\s+than\s+[^.;]+|excluding\s+[^.;]+|with\s+the\s+exception\s+of\s+[^.;]+)", re.IGNORECASE),
]

# --- Procedural Step Markers ---
STEP_RE = re.compile(
    r"(?i)\b(?:step\s+(\d+)|level\s+(\d+)|first\s+approach|escalat(?:e|ion)\s+to|lodge\s+(?:a\s+)?complaint\s+(?:on|with)|redressal\s+mechanism)\b"
)


def extract_conditions(text: str) -> list[Condition]:
    """Extract explicit preconditions from source text."""
    conditions: list[Condition] = []
    seen: set[str] = set()

    for pattern in CONDITION_PATTERNS:
        for m in pattern.finditer(text):
            cond_str = m.group(1).strip()
            # Clean trailing punctuation
            cond_str = re.sub(r"[,;]+$", "", cond_str).strip()
            if len(cond_str) > 10 and cond_str.lower() not in seen:
                seen.add(cond_str.lower())
                conditions.append(Condition(condition_text=cond_str))

    return conditions


def extract_exceptions(text: str) -> list[ExceptionClause]:
    """Extract explicit exceptions or exemptions from source text."""
    exceptions: list[ExceptionClause] = []
    seen: set[str] = set()

    for pattern in EXCEPTION_PATTERNS:
        for m in pattern.finditer(text):
            exc_str = m.group(1).strip()
            exc_str = re.sub(r"[,;]+$", "", exc_str).strip()
            if len(exc_str) > 8 and exc_str.lower() not in seen:
                seen.add(exc_str.lower())
                # Check for referenced provision in exception
                ref_match = CROSS_REF_RE.search(exc_str)
                ref_prov = ref_match.group(0) if ref_match else None
                exceptions.append(ExceptionClause(exception_text=exc_str, referenced_provision=ref_prov))

    return exceptions


def extract_timelines(text: str) -> list[Timeline]:
    """Extract explicit statutory or operational timelines."""
    timelines: list[Timeline] = []

    for m in TIMELINE_RE.finditer(text):
        qualifier = m.group(1).upper()
        duration_str = m.group(2)
        unit_raw = m.group(3).upper()

        unit = "DAYS"
        if "HOUR" in unit_raw:
            unit = "HOURS"
        elif "MONTH" in unit_raw:
            unit = "MONTHS"
        elif "WEEK" in unit_raw:
            unit = "WEEKS"
        elif "YEAR" in unit_raw:
            unit = "YEARS"

        if "WORKING" in unit_raw or "BUSINESS" in unit_raw:
            qualifier = "WORKING_DAYS"

        try:
            dur = float(duration_str) if "." in duration_str else int(duration_str)
        except ValueError:
            dur = None

        timelines.append(
            Timeline(
                duration=dur,
                unit=unit,
                qualifier=qualifier,
                timeline_text=m.group(0),
            )
        )

    return timelines


def extract_fees(text: str) -> list[FeeOrCharge]:
    """Extract fee, charge, tariff, or brokerage rates."""
    fees: list[FeeOrCharge] = []

    # Fixed amount regex
    for m in FEE_RE.finditer(text):
        amt_str = m.group(1) or m.group(2)
        unit = m.group(3).strip() if m.group(3) else None
        if amt_str:
            clean_amt = amt_str.replace(",", "")
            try:
                amt = float(clean_amt)
                fees.append(
                    FeeOrCharge(
                        amount=amt,
                        currency="INR",
                        unit=f"per {unit}" if unit else None,
                        charge_text=m.group(0).strip(),
                    )
                )
            except ValueError:
                pass

    # Percentage fee regex
    for m in PERCENTAGE_FEE_RE.finditer(text):
        pct_str = m.group(1)
        target = m.group(2).strip() if m.group(2) else None
        try:
            amt = float(pct_str)
            fees.append(
                FeeOrCharge(
                    amount=amt,
                    currency="INR",
                    unit="%",
                    applicability=target,
                    charge_text=m.group(0).strip(),
                )
            )
        except ValueError:
            pass

    return fees


def extract_definitions(text: str) -> list[Definition]:
    """Extract statutory or contractual definitions."""
    definitions: list[Definition] = []

    for m in DEFINITION_RE.finditer(text):
        term = m.group(1).strip()
        defn = m.group(2).strip()
        if len(term) >= 2 and len(defn) >= 5:
            definitions.append(
                Definition(
                    defined_term=term,
                    definition_text=defn,
                )
            )

    return definitions


def extract_cross_references(text: str) -> list[CrossReference]:
    """Extract citations to external regulatory instruments."""
    refs: list[CrossReference] = []
    seen: set[str] = set()

    for m in CROSS_REF_RE.finditer(text):
        full_ref = m.group(0).strip()
        if full_ref.lower() not in seen:
            seen.add(full_ref.lower())
            refs.append(
                CrossReference(
                    target_reference=full_ref,
                    relationship_type="REFERENCES",
                    resolved_status="CROSS_REFERENCE_UNRESOLVED",
                )
            )

    return refs


def extract_procedures(text: str) -> list[ProcedureStep]:
    """Extract sequential operational steps in grievance or administrative workflows."""
    steps: list[ProcedureStep] = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    step_counter = 1
    for line in lines:
        m = STEP_RE.search(line)
        if m:
            num = step_counter
            if m.group(1):
                num = int(m.group(1))
            elif m.group(2):
                num = int(m.group(2))

            escalation = None
            if "scores" in line.lower():
                escalation = "SCORES"
            elif "odr" in line.lower():
                escalation = "SMART_ODR"
            elif "sebi" in line.lower():
                escalation = "SEBI"

            steps.append(
                ProcedureStep(
                    step_number=num,
                    step_text=line,
                    escalation_path=escalation,
                )
            )
            step_counter = num + 1

    return steps


def classify_provision_type(
    text: str,
    heading: str | None = None,
    source_class: SourceClass = SourceClass.REGULATORY,
) -> ProvisionType:
    """Deterministically classify primary ProvisionType from text and contextual cues."""
    lower_text = text.lower()
    lower_heading = (heading or "").lower()

    # 1. Definitions
    if DEFINITION_RE.search(text) or "definition" in lower_heading:
        return ProvisionType.DEFINITION

    # 2. Fees & Charges
    if (
        "charge" in lower_heading
        or "brokerage" in lower_heading
        or "tariff" in lower_heading
        or "fee" in lower_heading
        or FEE_RE.search(text)
    ):
        if any(c in text for c in ["₹", "Rs", "brokerage", "tariff", "fee"]):
            return ProvisionType.FEE_OR_CHARGE

    # 3. Escalation / Grievance Procedures
    if "escalat" in lower_heading or "escalat" in lower_text or "grievance" in lower_heading:
        if "level" in lower_text or "matrix" in lower_text or "escalat" in lower_text:
            return ProvisionType.ESCALATION
        return ProvisionType.PROCEDURE

    # 4. Standalone Timeline
    if TIMELINE_RE.search(text) and len(text) < 150:
        return ProvisionType.TIMELINE

    # 5. Prohibitions
    if any(p in lower_text for p in ["shall not", "prohibited", "must not", "forbidden", "is barred from"]):
        return ProvisionType.PROHIBITION

    # 6. Obligations
    if any(o in lower_text for o in ["shall", "must", "mandatory", "required to", "is obligated to"]):
        return ProvisionType.OBLIGATION

    # 7. Rights & Entitlements
    if any(r in lower_text for r in ["entitled to", "right to", "may request", "investor rights"]):
        return ProvisionType.RIGHT

    # 8. Condition / Exception
    if text.strip().startswith(("Where", "If", "Provided that", "Subject to")):
        return ProvisionType.CONDITION
    if text.strip().startswith(("Except", "Save and except", "Other than")):
        return ProvisionType.EXCEPTION

    # 9. Procedures
    if STEP_RE.search(text) or "procedure" in lower_heading or "process" in lower_heading:
        return ProvisionType.PROCEDURE

    # 10. General / Scope
    if "scope" in lower_heading or "applicability" in lower_heading:
        return ProvisionType.SCOPE

    if source_class == SourceClass.REGULATORY:
        return ProvisionType.RULE

    return ProvisionType.GENERAL_INFORMATION


def extract_entities_and_process(text: str, topic: list[str]) -> tuple[list[str], str | None]:
    """Extract supported entities and primary financial/legal process."""
    lower = text.lower()
    entities: list[str] = []

    entity_map = {
        "investor": "investor",
        "client": "client",
        "stock broker": "stock_broker",
        "broker": "stock_broker",
        "depository participant": "depository_participant",
        "dp": "depository_participant",
        "depository": "depository",
        "trading member": "trading_member",
        "clearing member": "clearing_member",
        "exchange": "exchange",
        "sebi": "SEBI",
        "cdsl": "CDSL",
        "nsdl": "NSDL",
    }

    for k, v in entity_map.items():
        if re.search(rf"\b{re.escape(k)}\b", lower) and v not in entities:
            entities.append(v)

    process = None
    process_keywords = [
        ("grievance", "grievance"),
        ("complaint", "grievance"),
        ("scores", "scores"),
        ("odr", "odr"),
        ("account opening", "account_opening"),
        ("account closure", "account_closure"),
        ("close account", "account_closure"),
        ("dematerialisation", "dematerialisation"),
        ("demat", "demat_transfer"),
        ("transfer", "securities_transfer"),
        ("pledge", "pledge"),
        ("unpledge", "unpledge"),
        ("brokerage", "brokerage"),
        ("charges", "dp_charges"),
        ("trading", "trading"),
        ("settlement", "settlement"),
        ("corporate action", "corporate_action"),
        ("escalation", "escalation"),
    ]

    for kw, proc in process_keywords:
        if kw in lower:
            process = proc
            break

    return entities, process
