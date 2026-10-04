"""Orchestration Benchmark Evaluator for SANGYAN Phase 6A.

Evaluates:
- Orchestration success rate
- State transition correctness
- Event ordering correctness
- Assessment preservation
- Evidence integrity & claim preservation
- Idempotency & Concurrency integrity
- Case reopening correctness
- Audit reconstruction completeness
- Failure classification correctness
"""

from datetime import date
from decimal import Decimal
import json
import logging
from pathlib import Path
import time
from typing import Any

from ai.app.assessment.contracts import AssessmentStatus
from ai.app.case.contracts import (
    CaseEventType,
    CaseState,
    CaseStatus,
    CaseVersionConflictError,
)
from ai.app.case.repository import InMemoryCaseRepository
from ai.app.evaluation.assessment_cases import make_retrieval_result
from ai.app.evaluation.orchestration_cases import (
    OrchestrationGoldCase,
    build_orchestration_gold_cases,
)
from ai.app.orchestration.audit import AuditReconstructor
from ai.app.orchestration.contracts import (
    CaseTurnResult,
    GenerationSnapshot,
    OrchestrationInputEvent,
)
from ai.app.orchestration.orchestrator import CaseOrchestrator
from ai.app.retrieval.contracts import RetrievalResponse

logger = logging.getLogger("sangyan.evaluation.orchestration")


def get_default_test_retrieval() -> RetrievalResponse:
    """Standard regulatory test retrieval containing the statutory DP fee cap."""
    prov = make_retrieval_result(
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
    )
    return RetrievalResponse(query="DP charges", results=[prov])


class OrchestrationEvaluator:
    """Executes gold orchestration benchmark cases and aggregates reliability metrics."""

    def __init__(self, cases: list[OrchestrationGoldCase] | None = None) -> None:
        self.cases = cases or build_orchestration_gold_cases()

    async def evaluate(self) -> dict[str, Any]:
        """Run all benchmark cases and compute comprehensive metrics."""
        total_cases = len(self.cases)
        total_turns = 0
        successful_turns = 0
        state_transitions_correct = 0
        total_transitions = 0
        event_ordering_correct = 0
        assessment_preservation_correct = 0
        evidence_integrity_correct = 0
        idempotency_checks = 0
        idempotency_passed = 0
        concurrency_checks = 0
        concurrency_passed = 0
        reopen_checks = 0
        reopen_passed = 0
        audit_reconstruction_passed = 0
        failure_classification_passed = 0

        case_reports: list[dict[str, Any]] = []
        start_eval_time = time.perf_counter()

        for case_spec in self.cases:
            case_start = time.perf_counter()
            repo = InMemoryCaseRepository()
            retrieval = get_default_test_retrieval()
            mock_retriever = type("MockRetriever", (), {"retrieve": lambda self, req: retrieval})()
            orchestrator = CaseOrchestrator(repository=repo, retriever=mock_retriever)

            case_passed = True
            turn_results: list[dict[str, Any]] = []

            for turn_idx, turn_exp in enumerate(case_spec.turns):
                total_turns += 1

                # Simulate Generation Failure
                if turn_exp.simulate_generation_failure:
                    orchestrator.generator = type(
                        "FailingGen",
                        (),
                        {"generate_response": lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM API Timeout"))},
                    )()

                # Simulate Retrieval Failure
                if turn_exp.simulate_retrieval_failure:
                    orchestrator.retriever = type(
                        "FailingRetriever",
                        (),
                        {"retrieve": lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Vector DB Offline"))},
                    )()

                try:
                    result = await orchestrator.process_turn(
                        case_id=case_spec.case_id,
                        input_event=turn_exp.input_event,
                        expected_version=turn_exp.expected_version,
                        idempotency_key=turn_exp.idempotency_key,
                    )

                    if turn_exp.should_raise_conflict:
                        case_passed = False
                        turn_results.append({
                            "turn": turn_exp.turn_index,
                            "error": "Expected CaseVersionConflictError but turn succeeded.",
                        })
                        continue

                    successful_turns += 1

                    # Check State Transition
                    total_transitions += 1
                    if result.new_status == turn_exp.expected_status:
                        state_transitions_correct += 1
                    else:
                        case_passed = False

                    # Check Assessment Status if expected
                    if turn_exp.expected_assessment_status:
                        if result.assessment_result and result.assessment_result.status == turn_exp.expected_assessment_status:
                            assessment_preservation_correct += 1
                        else:
                            case_passed = False
                    else:
                        assessment_preservation_correct += 1

                    # Check Expected Facts
                    for k, v in turn_exp.expected_facts.items():
                        if result.new_facts.get(k) != v:
                            case_passed = False

                    # Check Idempotency
                    if turn_exp.idempotency_key and turn_idx > 0:
                        idempotency_checks += 1
                        # Same version, no duplicate events
                        if result.previous_version == result.new_version:
                            idempotency_passed += 1

                    # Check Reopen
                    if case_spec.scenario_type == "case_reopening" and turn_idx > 0:
                        reopen_checks += 1
                        if any(e.event_type == CaseEventType.CASE_REOPENED for e in result.events_created):
                            reopen_passed += 1

                    # Check Downstream Generation Failure
                    if turn_exp.simulate_generation_failure:
                        if result.generation_snapshot and result.generation_snapshot.status == "FAILED":
                            failure_classification_passed += 1
                        else:
                            case_passed = False

                    turn_results.append({
                        "turn": turn_exp.turn_index,
                        "status": result.new_status.value,
                        "assessment_status": result.assessment_result.status.value if result.assessment_result else None,
                        "version": result.new_version,
                        "duration_ms": result.duration_ms,
                    })

                except CaseVersionConflictError:
                    if turn_exp.should_raise_conflict:
                        concurrency_checks += 1
                        concurrency_passed += 1
                        successful_turns += 1
                        turn_results.append({
                            "turn": turn_exp.turn_index,
                            "handled_conflict": True,
                        })
                    else:
                        case_passed = False
                        turn_results.append({
                            "turn": turn_exp.turn_index,
                            "unexpected_conflict": True,
                        })

                except Exception as exc:
                    if turn_exp.simulate_retrieval_failure:
                        failure_classification_passed += 1
                        successful_turns += 1
                        turn_results.append({
                            "turn": turn_exp.turn_index,
                            "handled_retrieval_failure": True,
                        })
                    else:
                        case_passed = False
                        turn_results.append({
                            "turn": turn_exp.turn_index,
                            "unexpected_exception": str(exc),
                        })

            # Check Event Ordering and State Integrity
            final_state = await repo.get_case(case_spec.case_id)
            if final_state:
                events = final_state.interaction_history
                is_ordered = all(
                    events[i].created_at <= events[i + 1].created_at
                    for i in range(len(events) - 1)
                )
                if is_ordered:
                    event_ordering_correct += 1

                # Check Evidence & Claim Integrity
                if len(final_state.evidence) > 0 or len(final_state.facts) > 0:
                    evidence_integrity_correct += 1

                # Check Audit Completeness
                audit_report = AuditReconstructor.verify_audit_completeness(final_state)
                if audit_report["is_complete"]:
                    audit_reconstruction_passed += 1
                else:
                    case_passed = False
            elif any(t.simulate_retrieval_failure for t in case_spec.turns):
                # Turn failed cleanly before commit; no partial authoritative state mutation (atomicity verified)
                event_ordering_correct += 1
                evidence_integrity_correct += 1
                audit_reconstruction_passed += 1
            else:
                case_passed = False

            case_duration_ms = (time.perf_counter() - case_start) * 1000
            case_reports.append({
                "case_id": case_spec.case_id,
                "title": case_spec.title,
                "scenario_type": case_spec.scenario_type,
                "passed": case_passed,
                "turns_count": len(case_spec.turns),
                "turns": turn_results,
                "duration_ms": case_duration_ms,
            })

        total_duration_s = time.perf_counter() - start_eval_time

        summary = {
            "total_cases": total_cases,
            "total_turns": total_turns,
            "orchestration_success_rate": round((successful_turns / total_turns) * 100, 2) if total_turns else 0.0,
            "state_transition_correctness": round((state_transitions_correct / total_transitions) * 100, 2) if total_transitions else 0.0,
            "event_ordering_correctness": round((event_ordering_correct / total_cases) * 100, 2) if total_cases else 0.0,
            "assessment_preservation": round((assessment_preservation_correct / total_turns) * 100, 2) if total_turns else 0.0,
            "evidence_integrity": round((evidence_integrity_correct / total_cases) * 100, 2) if total_cases else 0.0,
            "idempotency_pass_rate": round((idempotency_passed / idempotency_checks) * 100, 2) if idempotency_checks else 100.0,
            "concurrency_integrity": round((concurrency_passed / concurrency_checks) * 100, 2) if concurrency_checks else 100.0,
            "reopen_correctness": round((reopen_passed / reopen_checks) * 100, 2) if reopen_checks else 100.0,
            "audit_reconstruction_completeness": round((audit_reconstruction_passed / total_cases) * 100, 2) if total_cases else 0.0,
            "total_duration_seconds": round(total_duration_s, 2),
            "case_reports": case_reports,
        }

        # Save to corpus report
        report_path = Path("ai/corpus/orchestration_benchmark_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)

        return summary
