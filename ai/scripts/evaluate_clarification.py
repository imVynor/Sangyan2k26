"""Execute SANGYAN Phase 5 Multi-Turn Clarification Benchmark Evaluation.

Outputs formatted benchmark report and writes machine-readable JSON:
`ai/corpus/clarification_benchmark_report.json`
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.stdout.reconfigure(encoding="utf-8")

from ai.app.evaluation.clarification_cases import GOLD_CLARIFICATION_CASES
from ai.app.evaluation.clarification_evaluator import ClarificationEvaluator


async def main() -> None:
    print("=" * 70)
    print("SANGYAN Phase 5 Multi-Turn Clarification Benchmark Evaluation")
    print("=" * 70)

    evaluator = ClarificationEvaluator()
    print(f"[BENCHMARK] Executing {len(GOLD_CLARIFICATION_CASES)} gold multi-turn cases...")
    start_time = time.perf_counter()

    summary = await evaluator.evaluate_all(cases=GOLD_CLARIFICATION_CASES)
    duration = time.perf_counter() - start_time

    print("\n" + "=" * 70)
    print("SANGYAN Clarification Benchmark Evaluation Summary")
    print("=" * 70)
    print(f"Total Cases:                   {summary['total_cases']}")
    print(f"Clarification Precision:       {summary['clarification_precision'] * 100:.1f}%")
    print(f"Clarification Recall:          {summary['clarification_recall'] * 100:.1f}%")
    print(f"Question Efficiency (Avg Rds): {summary['question_efficiency_avg_rounds']}")
    print(f"Assessment Preservation:       {summary['assessment_preservation'] * 100:.1f}%")
    print(f"State Integrity:               {summary['state_integrity'] * 100:.1f}%")
    print(f"Idempotency Rate:              {summary['idempotency_rate'] * 100:.1f}%")
    print(f"Concurrency Integrity:         {summary['concurrency_integrity'] * 100:.1f}%")
    print(f"Contradiction Handling:        {summary['contradiction_handling_rate'] * 100:.1f}%")
    print(f"Execution Duration:            {duration:.2f}s")
    print("-" * 70)

    discrepancies = [
        c for c in summary["cases"]
        if not c["assessment_preserved"] or not c["state_integrity"] or not c["idempotency_pass"]
    ]

    if discrepancies:
        print(f"\n[WARNING] Found {len(discrepancies)} cases with discrepancies:")
        for d in discrepancies:
            print(f"  - Case {d['case_id']}: Expected '{d['expected_final_status']}', got '{d['final_status']}'")
    else:
        print("\nAll 20 multi-turn gold benchmark cases passed with zero discrepancies!")

    report_path = Path("ai/corpus/clarification_benchmark_report.json").resolve()
    print(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
