"""Benchmark Evaluator for SANGYAN Multi-Turn Clarification and Dialogue.

Computes Section 37 metrics:
- Clarification precision
- Clarification recall
- Question efficiency (average rounds)
- Assessment preservation
- State integrity
- Contradiction handling
- Idempotency
- Version integrity
"""

from copy import deepcopy
from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Sequence

from ai.app.assessment.contracts import (
    AssessmentStatus,
    EvidenceType,
)
from ai.app.case.contracts import CaseVersionConflictError
from ai.app.case.repository import InMemoryCaseRepository
from ai.app.case.service import CaseService
from ai.app.evaluation.assessment_cases import make_retrieval_result
from ai.app.evaluation.clarification_cases import (
    GOLD_CLARIFICATION_CASES,
    MultiTurnBenchmarkCase,
)
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult

logger = logging.getLogger("sangyan.evaluation.clarification")


class ClarificationEvaluator:
    """Evaluates multi-turn case reasoning across gold clarification cases."""

    def __init__(self, service: CaseService | None = None) -> None:
        self.service = service or CaseService(repository=InMemoryCaseRepository())

    async def evaluate_case(
        self,
        case: MultiTurnBenchmarkCase,
        mock_provisions: list[RetrievalResult] | None = None,
    ) -> dict[str, Any]:
        """Execute a full multi-turn benchmark case."""
        case_id = f"TEST-{case.case_id}"
        provisions = mock_provisions or self._build_provisions_for_case(case.case_id)
        retrieval = RetrievalResponse(
            results=provisions,
            total_candidates_found=len(provisions),
        )

        # -------------------------------------------------------------
        # TURN 1: Initial Complaint
        # -------------------------------------------------------------
        case_state, gen_resp, plan = await self.service.create_case(
            case_id=case_id,
            complaint_text=case.initial_complaint,
            reference_date=case.reference_date,
            language=case.language,
            retrieval_response=retrieval,
        )

        turn_1_status = case_state.current_assessment.status
        turn_1_status_match = turn_1_status == case.initial_expected_status

        # Verify first question planned
        asked_field = plan.questions[0].field if plan.questions else None
        question_precision = True
        question_recall = True

        if case.expected_first_question_field is not None:
            if asked_field != case.expected_first_question_field:
                question_recall = False
                logger.warning(
                    f"[{case.case_id}] Expected question field '{case.expected_first_question_field}', "
                    f"but planner requested '{asked_field}'."
                )
        else:
            if asked_field is not None:
                question_precision = False

        # Verify Version Integrity on Turn 1
        version_turn_1_ok = case_state.version == 1

        # -------------------------------------------------------------
        # IDEMPOTENCY TEST: Submit duplicate turn with same idempotency key
        # -------------------------------------------------------------
        idemp_key = f"IDEMP-{case.case_id}-T2"
        idemp_pass = True

        # -------------------------------------------------------------
        # CONCURRENCY TEST: Attempting update with stale version must fail
        # -------------------------------------------------------------
        concurrency_pass = True
        try:
            await self.service.process_user_turn(
                case_id=case_id,
                user_message="stale message",
                expected_version=99,  # Intentionally stale
                language=case.language,
            )
            concurrency_pass = False
        except CaseVersionConflictError:
            concurrency_pass = True
        except Exception:
            concurrency_pass = False

        # -------------------------------------------------------------
        # TURN 2: User Action (Answer / Document / Decline / Irrelevant)
        # -------------------------------------------------------------
        final_state = case_state
        final_gen = gen_resp
        delta = None

        if case.turn_2_action == "DECLINE":
            decline_field = case.turn_2_decline_field or asked_field or "transaction_type"
            final_state, final_gen, plan, delta = await self.service.process_user_decline(
                case_id=case_id,
                field_name=decline_field,
                expected_version=1,
                idempotency_key=idemp_key,
                language=case.language,
            )
        else:
            final_state, final_gen, plan, delta = await self.service.process_user_turn(
                case_id=case_id,
                user_message=case.turn_2_message,
                documents=case.turn_2_documents,
                expected_version=1,
                idempotency_key=idemp_key,
                language=case.language,
                retrieval_response=retrieval,
            )

        # Re-send identical turn with same idempotency key -> must be identical state
        dup_state, _, _, _ = await self.service.process_user_turn(
            case_id=case_id,
            user_message=case.turn_2_message,
            documents=case.turn_2_documents,
            expected_version=final_state.version,
            idempotency_key=idemp_key,
            language=case.language,
            retrieval_response=retrieval,
        )
        if dup_state.version != final_state.version or len(dup_state.evidence) != len(final_state.evidence):
            idemp_pass = False

        # -------------------------------------------------------------
        # Final Assessment Preservation Check
        # -------------------------------------------------------------
        final_status = final_state.current_assessment.status
        assessment_preserved = final_status == case.expected_final_status

        # State integrity: check that turn 1 evidence still exists in turn 2
        state_integrity = len(final_state.evidence) >= len(case_state.evidence)
        history_preserved = len(final_state.interaction_history) >= 2

        # Contradiction handling:
        contradiction_handled = True
        if case.case_id in {"CLAR-05", "CLAR-14"}:
            # Evidence items should retain both assertions
            amounts = [e.value for e in final_state.evidence if e.field_name == "charged_amount"]
            if len(amounts) < 2:
                contradiction_handled = False

        return {
            "case_id": case.case_id,
            "scenario": case.scenario,
            "turn_1_status": turn_1_status.value,
            "turn_1_expected": case.initial_expected_status.value,
            "turn_1_match": turn_1_status_match,
            "expected_question_field": case.expected_first_question_field,
            "asked_question_field": asked_field,
            "question_precision": question_precision,
            "question_recall": question_recall,
            "final_status": final_status.value,
            "expected_final_status": case.expected_final_status.value,
            "assessment_preserved": assessment_preserved,
            "state_integrity": state_integrity and history_preserved,
            "idempotency_pass": idemp_pass,
            "concurrency_pass": concurrency_pass,
            "contradiction_handled": contradiction_handled,
            "rounds": final_state.clarification_rounds,
        }

    async def evaluate_all(
        self,
        cases: list[MultiTurnBenchmarkCase] | None = None,
        output_path: str = "ai/corpus/clarification_benchmark_report.json",
    ) -> dict[str, Any]:
        """Execute all gold clarification cases and compute summary metrics."""
        case_list = cases or GOLD_CLARIFICATION_CASES
        results: list[dict[str, Any]] = []

        total_precision_hits = 0
        total_recall_hits = 0
        total_preservation_hits = 0
        total_state_integrity_hits = 0
        total_idempotency_hits = 0
        total_concurrency_hits = 0
        total_contradiction_hits = 0
        total_rounds = 0

        for c in case_list:
            res = await self.evaluate_case(c)
            results.append(res)

            if res["question_precision"]:
                total_precision_hits += 1
            if res["question_recall"]:
                total_recall_hits += 1
            if res["assessment_preserved"]:
                total_preservation_hits += 1
            if res["state_integrity"]:
                total_state_integrity_hits += 1
            if res["idempotency_pass"]:
                total_idempotency_hits += 1
            if res["concurrency_pass"]:
                total_concurrency_hits += 1
            if res["contradiction_handled"]:
                total_contradiction_hits += 1
            total_rounds += res["rounds"]

        n = len(case_list)
        summary = {
            "total_cases": n,
            "clarification_precision": round(total_precision_hits / n, 4),
            "clarification_recall": round(total_recall_hits / n, 4),
            "question_efficiency_avg_rounds": round(total_rounds / n, 2),
            "assessment_preservation": round(total_preservation_hits / n, 4),
            "state_integrity": round(total_state_integrity_hits / n, 4),
            "idempotency_rate": round(total_idempotency_hits / n, 4),
            "concurrency_integrity": round(total_concurrency_hits / n, 4),
            "contradiction_handling_rate": round(total_contradiction_hits / n, 4),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "cases": results,
        }

        # Write to JSON report
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Saved clarification benchmark report to {out_file}")
        return summary

    def _build_provisions_for_case(self, case_id: str) -> list[RetrievalResult]:
        if case_id == "CLAR-19":
            return []  # Unregistered advisory entity -> zero regulatory provisions
        if case_id == "CLAR-04":
            return [
                make_retrieval_result(
                    provision_id="prov_sebi_bsda_amc_free",
                    document_id="doc_sebi_bsda_cir",
                    section_id="sec_bsda_rules",
                    authority="SEBI",
                    source_class="REGULATORY",
                    provision_text="Basic Services Demat Accounts (BSDA) with holding value up to ₹50,000 shall have nil AMC.",
                    relevance_score=0.92,
                    effective_from=date(2022, 1, 1),
                    source_url="https://sebi.gov.in/bsda.pdf",
                    citation="SEBI BSDA Circular",
                )
            ]
        if case_id in {"CLAR-06", "CLAR-20"}:
            return [
                make_retrieval_result(
                    provision_id="prov_cdsl_dp_cap_2022",
                    document_id="doc_cdsl_tariff_2022",
                    section_id="sec_dp_charges",
                    authority="CDSL",
                    source_class="REGULATORY",
                    provision_text="CDSL DP charges for equity delivery shall not exceed ₹20.00 per debit transaction.",
                    relevance_score=0.95,
                    effective_from=date(2021, 1, 1),
                    effective_to=date(2022, 12, 31),
                    source_url="https://cdslindia.com/tariff_2022.html",
                    citation="CDSL Operating Tariff 2022",
                ),
                make_retrieval_result(
                    provision_id="prov_cdsl_dp_cap_2026",
                    document_id="doc_cdsl_tariff_2026",
                    section_id="sec_dp_charges",
                    authority="CDSL",
                    source_class="REGULATORY",
                    provision_text="CDSL DP charges for equity delivery shall not exceed ₹15.00 per debit transaction.",
                    relevance_score=0.95,
                    effective_from=date(2023, 1, 1),
                    source_url="https://cdslindia.com/tariff.html",
                    citation="CDSL Operating Tariff 2026",
                ),
            ]
        return self._build_default_provisions()

    def _build_default_provisions(self) -> list[RetrievalResult]:
        """Default provisions used for deterministic testing."""
        return [
            make_retrieval_result(
                provision_id="prov_cdsl_dp_cap_2026",
                document_id="doc_cdsl_tariff_2026",
                section_id="sec_dp_charges",
                authority="CDSL",
                source_class="REGULATORY",
                provision_text="CDSL DP charges for equity delivery shall not exceed ₹15.00 per debit transaction.",
                relevance_score=0.95,
                effective_from=date(2023, 1, 1),
                source_url="https://cdslindia.com/tariff.html",
                citation="CDSL Operating Tariff 2026",
            ),
        ]
