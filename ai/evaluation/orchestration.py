"""CLI runner for SANGYAN Orchestration Benchmark (Phase 6A)."""

import asyncio
import sys

from ai.app.evaluation.orchestration_evaluator import OrchestrationEvaluator


async def main() -> None:
    print("=" * 70)
    print("SANGYAN Phase 6A: Case Orchestrator Benchmark Evaluation")
    print("=" * 70)

    evaluator = OrchestrationEvaluator()
    summary = await evaluator.evaluate()

    print(f"Total Cases Evaluated:              {summary['total_cases']}")
    print(f"Total Turns Executed:               {summary['total_turns']}")
    print(f"Orchestration Success Rate:         {summary['orchestration_success_rate']}%")
    print(f"State Transition Correctness:       {summary['state_transition_correctness']}%")
    print(f"Event Ordering Correctness:         {summary['event_ordering_correctness']}%")
    print(f"Assessment Preservation:            {summary['assessment_preservation']}%")
    print(f"Evidence & Claim Integrity:         {summary['evidence_integrity']}%")
    print(f"Idempotency Pass Rate:              {summary['idempotency_pass_rate']}%")
    print(f"Concurrency Integrity:              {summary['concurrency_integrity']}%")
    print(f"Case Reopen Correctness:            {summary['reopen_correctness']}%")
    print(f"Audit Reconstruction Completeness:  {summary['audit_reconstruction_completeness']}%")
    print(f"Total Evaluation Time:              {summary['total_duration_seconds']}s")
    print("=" * 70)

    failed_cases = [c for c in summary["case_reports"] if not c["passed"]]
    if failed_cases:
        print(f"\nDiscrepancies / Failures ({len(failed_cases)}):")
        for fc in failed_cases:
            print(f"  [{fc['case_id']}] {fc['title']} - Turns: {fc['turns']}")
        sys.exit(1)
    else:
        print("\nAll 20 gold orchestration benchmark cases PASSED with zero discrepancies!")
        print("Report saved: ai/corpus/orchestration_benchmark_report.json\n")


if __name__ == "__main__":
    asyncio.run(main())
