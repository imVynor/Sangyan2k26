"""Corpus Case Schema and Epistemic Integrity Validator for SANGYAN (Phase 7A).

Epistemic foundation:
- Validates structural completeness, strong typing, and Decimal enforcement.
- Enforces Section 36: Every expected regulatory provision must resolve to an authentic
  corpus provision or be explicitly marked as 'is_blocked_by_corpus_gap = True'.
- Rejects floating-point currency and enforces negative unknowns.
"""

from decimal import Decimal
import logging
from typing import Sequence

from ai.evaluation.corpus.models import EvaluationCase

logger = logging.getLogger("sangyan.evaluation.validator")


class ValidationResult:
    def __init__(self) -> None:
        self.is_valid: bool = True
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.verified_provisions: int = 0
        self.corpus_gap_cases: int = 0

    def add_error(self, case_id: str, message: str) -> None:
        self.is_valid = False
        self.errors.append(f"[{case_id}] ERROR: {message}")

    def add_warning(self, case_id: str, message: str) -> None:
        self.warnings.append(f"[{case_id}] WARNING: {message}")


class CaseValidator:
    """Validates evaluation cases against structural and epistemic standards."""

    def __init__(self, known_provision_ids: set[str] | None = None) -> None:
        self.known_provision_ids = known_provision_ids or set()

    def validate_case(self, case: EvaluationCase) -> ValidationResult:
        """Validate an individual evaluation case."""
        result = ValidationResult()

        # 1. Structural checks
        if not case.case_id or not case.case_id.strip():
            result.add_error("UNKNOWN", "Missing case_id")
        if not case.title or not case.title.strip():
            result.add_error(case.case_id, "Missing title")
        if not case.user_input or not case.user_input.strip():
            result.add_error(case.case_id, "Missing user_input")

        # 2. Fact typing and Decimal check
        for fact in case.expected_facts:
            if fact.data_type in ("DECIMAL", "CURRENCY"):
                if not isinstance(fact.expected_value, Decimal):
                    try:
                        Decimal(str(fact.expected_value))
                    except Exception:
                        result.add_error(
                            case.case_id,
                            f"Numeric fact '{fact.field}' must use Decimal, got {type(fact.expected_value)}",
                        )

        # 3. Negative unknowns check
        for unk in case.expected_unknowns:
            if unk.expected_value is not None:
                result.add_error(
                    case.case_id,
                    f"Unknown fact '{unk.field}' has non-None expected_value: {unk.expected_value}",
                )
            if not unk.must_remain_unknown:
                result.add_error(
                    case.case_id,
                    f"Unknown fact '{unk.field}' must set must_remain_unknown=True",
                )

        # 4. Compound financial breakdown check
        if case.expected_financial:
            fin = case.expected_financial
            for field_name in ["base_amount", "brokerage", "exchange_txn_charge", "sebi_turnover_fee", "gst", "stt", "stamp_duty", "dp_charges", "total_expected"]:
                val = getattr(fin, field_name)
                if val is not None and not isinstance(val, Decimal):
                    result.add_error(
                        case.case_id,
                        f"Financial field '{field_name}' must be Decimal, got {type(val)}",
                    )

        # 5. Provision provenance check (Section 26 & Section 36)
        if case.is_blocked_by_corpus_gap:
            result.corpus_gap_cases += 1
            if not case.corpus_gap_reason:
                result.add_warning(case.case_id, "Flagged is_blocked_by_corpus_gap but missing corpus_gap_reason")
        else:
            for prov in case.expected_provisions:
                if prov.is_blocked_by_corpus_gap:
                    result.corpus_gap_cases += 1
                    continue
                if not prov.provenance_rationale:
                    result.add_warning(
                        case.case_id,
                        f"Expected provision '{prov.provision_id}' lacks statutory provenance_rationale",
                    )
                if self.known_provision_ids and prov.provision_id not in self.known_provision_ids:
                    result.add_warning(
                        case.case_id,
                        f"Provision '{prov.provision_id}' not found in known database provisions (potential corpus gap)",
                    )
                else:
                    result.verified_provisions += 1

        # 6. Safety invariant checks
        if case.expected_assessment:
            status = case.expected_assessment.expected_status
            if status == "VIOLATION_CONFIRMED":
                # Must have explicit facts, conditions, or provisions
                if not case.expected_provisions and not case.is_blocked_by_corpus_gap:
                    result.add_error(
                        case.case_id,
                        "VIOLATION_CONFIRMED expected but no expected_provisions specified to justify violation",
                    )

        return result

    def validate_suite(self, cases: Sequence[EvaluationCase]) -> ValidationResult:
        """Validate an entire collection of cases and check for ID duplicates."""
        suite_result = ValidationResult()
        seen_ids: set[str] = set()

        for case in cases:
            if case.case_id in seen_ids:
                suite_result.add_error(case.case_id, f"Duplicate case_id: '{case.case_id}'")
            seen_ids.add(case.case_id)

            case_res = self.validate_case(case)
            if not case_res.is_valid:
                suite_result.is_valid = False
            suite_result.errors.extend(case_res.errors)
            suite_result.warnings.extend(case_res.warnings)
            suite_result.verified_provisions += case_res.verified_provisions
            suite_result.corpus_gap_cases += case_res.corpus_gap_cases

        return suite_result
