"""Evaluation Suite Runner and Benchmark Reporter for SANGYAN (Phase 7A).

Usage:
    python -m ai.evaluation.runners.evaluate_suite --suite all
    python -m ai.evaluation.runners.evaluate_suite --suite retrieval
    python -m ai.evaluation.runners.evaluate_suite --suite assessment
    python -m ai.evaluation.runners.evaluate_suite --suite adversarial
    python -m ai.evaluation.runners.evaluate_suite --suite multilingual
    python -m ai.evaluation.runners.evaluate_suite --suite temporal
    python -m ai.evaluation.runners.evaluate_suite --suite cross-document
    python -m ai.evaluation.runners.evaluate_suite --case BASIC-001
    python -m ai.evaluation.runners.evaluate_suite --output ai/evaluation/reports/baseline_report.json
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys
import time

from ai.app.orchestration.orchestrator import CaseOrchestrator
from ai.evaluation.corpus.loader import CorpusLoader
from ai.evaluation.evaluators.aggregate import BenchmarkAggregator
from ai.evaluation.runners.evaluate_case import SingleCaseEvaluator

logger = logging.getLogger("sangyan.evaluation.runner.suite")

DEFAULT_REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"


async def run_evaluation_suite(
    suite: str = "all",
    category: str | None = None,
    difficulty: str | None = None,
    visibility: str = "PUBLIC",
    case_id: str | None = None,
    model: str = "sangyan-deterministic-v1",
    output_path: Path | None = None,
    run_label: str = "7B-REAL-RETRIEVAL",
) -> int:
    """Execute evaluation cases and generate formatted terminal and JSON reports."""
    loader = CorpusLoader()
    cases = loader.filter_cases(
        suite=suite,
        category=category,
        difficulty=difficulty,
        visibility=visibility,
        case_id=case_id,
    )

    if not cases:
        print(f"\n[ERROR] No cases found matching criteria: suite={suite}, category={category}, case_id={case_id}")
        return 1

    print("\n" + "=" * 65)
    print("SANGYAN Adversarial Evaluation Framework (Phase 7A)")
    print(f"Executing Suite: '{suite}' | Total Cases: {len(cases)} | Model: {model}")
    print("=" * 65)

    # Default CaseOrchestrator() => real DefaultProvisionRetriever (PostgreSQL + pgvector).
    orchestrator = CaseOrchestrator()
    # Raises MockRetrieverInRealBenchmarkError if anything but the real retriever is wired.
    evaluator = SingleCaseEvaluator(orchestrator=orchestrator, require_real_retriever=True)
    print(f"Run label: {run_label} | Retriever: {type(orchestrator.retriever).__name__}")

    case_reports = []
    start_time = time.perf_counter()

    for idx, case in enumerate(cases, start=1):
        try:
            report = await evaluator.evaluate_case(case)
            case_reports.append(report)
            status_symbol = "[PASS]" if report.overall_passed else "[FAIL]"
            fail_reason = f" ({report.failure_class})" if not report.overall_passed and report.failure_class else ""
            title_clean = case.title.replace("\u20b9", "Rs ")
            print(f"[{idx:02d}/{len(cases):02d}] {case.case_id:12s} {status_symbol} {title_clean[:40]:40s}{fail_reason}")
        except Exception as e:
            logger.error(f"Error evaluating case {case.case_id}: {e}", exc_info=True)
            print(f"[{idx:02d}/{len(cases):02d}] {case.case_id:12s} [ERROR] Execution failed: {e}")

    total_duration = time.perf_counter() - start_time

    # Aggregate results
    diag_cases = [c for c in case_reports if c.retrieval_diagnostics]
    total_results = sum(c.retrieval_diagnostics.get("result_count", 0) for c in diag_cases)
    resolved = sum(c.retrieval_diagnostics.get("citations_resolved", 0) for c in diag_cases)
    causal_counts: dict[str, int] = {}
    for c in case_reports:
        if not c.overall_passed:
            key = c.failure_class or "OTHER"
            causal_counts[key] = causal_counts.get(key, 0) + 1
    metadata = {
        "run_label": run_label,
        "retriever_class": type(orchestrator.retriever).__name__,
        "retrieval_mode": "real_postgres_pgvector_hybrid",
        "model": model,
        "embedding_model": "nomic-embed-text:v1.5 (Ollama)",
        "knowledge_snapshot": "KNOW-2026-V1",
        "benchmark_version": "7B-1.0",
        "total_duration_sec": round(total_duration, 2),
        "citation_resolution_rate": round(resolved / total_results, 4) if total_results else 0.0,
        "causal_failure_counts": causal_counts,
        "operational_failures": [c.case_id for c in case_reports if c.failure_class == "OPERATIONAL_FAILURE"],
        "cases_with_empty_retrieval": sum(1 for c in diag_cases if c.retrieval_diagnostics.get("result_count", 0) == 0),
    }

    summary = BenchmarkAggregator.aggregate(
        case_reports=case_reports,
        suite_id=f"SUITE-{suite.upper()}",
        metadata=metadata,
    )

    # Format human-readable output (Section 29)
    print("\n" + "=" * 65)
    print("SANGYAN Evaluation Summary")
    print("=" * 65)
    print(f"Total Cases Evaluated:         {summary.total_cases}")
    print(f"Cases Passed:                  {summary.passed_cases} ({summary.accuracy * 100:.1f}%)")
    print(f"Cases Failed:                  {summary.failed_cases}")
    print("-" * 65)
    print("STAGE METRICS:")
    print(f"  FACT EXTRACTION Accuracy:    {summary.fact_accuracy * 100:.1f}%")
    print(f"  UNKNOWN INTEGRITY:           {summary.fact_unknown_accuracy * 100:.1f}%")
    print(f"  ISSUE IDENTIFICATION:")
    print(f"    Precision:                 {summary.issue_precision * 100:.1f}%")
    print(f"    Recall:                    {summary.issue_recall * 100:.1f}%")
    print(f"  PROVISION RETRIEVAL:")
    print(f"    Recall@1:                  {summary.retrieval_recall_at_1 * 100:.1f}%")
    print(f"    Recall@5:                  {summary.retrieval_recall_at_5 * 100:.1f}%")
    print(f"    Recall@10:                 {summary.retrieval_recall_at_10 * 100:.1f}%")
    print(f"    Recall@20:                 {summary.retrieval_recall_at_20 * 100:.1f}%")
    print(f"    MRR:                       {summary.retrieval_mrr:.3f}")
    print(f"    nDCG@10:                   {summary.retrieval_ndcg_at_10:.3f}")
    print(f"    Required-Provision Recall: {summary.retrieval_required_recall * 100:.1f}%")
    print(f"  TEMPORAL REASONING:")
    print(f"    Correct Version Accuracy:  {summary.temporal_correctness * 100:.1f}%")
    print(f"  EVIDENCE & CONTRADICTIONS:")
    print(f"    Contradiction Detection:   {summary.evidence_contradiction_accuracy * 100:.1f}%")
    print(f"  EPISTEMIC ASSESSMENT:")
    print(f"    Status Accuracy:           {summary.assessment_status_accuracy * 100:.1f}%")
    print(f"    Condition Accuracy:        {summary.condition_accuracy * 100:.1f}%")
    print(f"    Numerical (Decimal):       {summary.numerical_accuracy * 100:.1f}%")
    print(f"  CLARIFICATION DIALOGUE:")
    print(f"    Precision:                 {summary.clarification_precision * 100:.1f}%")
    print(f"    Recall:                    {summary.clarification_recall * 100:.1f}%")
    print(f"    Unnecessary Question Rate: {summary.unnecessary_question_rate * 100:.1f}%")
    print(f"  GROUNDING & CITATIONS:")
    print(f"    Unsupported Claim Rate:    {summary.grounding_unsupported_claim_rate * 100:.1f}%")
    print("-" * 65)
    print("SAFETY-CRITICAL INVARIANT AUDIT:")
    print(f"  False Positive Violations:   {summary.false_positive_violations} (MUST BE 0)")
    print(f"  False Positive Compliances:  {summary.false_positive_compliances} (MUST BE 0)")
    print("-" * 65)
    print("PERFORMANCE BY DIFFICULTY:")
    for diff, stats in sorted(summary.difficulty_performance.items()):
        print(f"  {diff}: {stats['passed']}/{stats['total']} passed ({stats['accuracy'] * 100:.1f}%)")
    print("-" * 65)
    print("FAILURE TAXONOMY BREAKDOWN:")
    for f_class, count in sorted(summary.failure_class_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {f_class:30s}: {count}")

    # Persist JSON report
    report_target = output_path or (DEFAULT_REPORT_DIR / f"run_{suite}_{int(time.time())}.json")
    report_target.parent.mkdir(parents=True, exist_ok=True)

    with open(report_target, "w", encoding="utf-8") as f:
        f.write(summary.model_dump_json(indent=2))

    print(f"\nMachine-readable benchmark report saved to: {report_target.resolve()}\n")

    # Safety alert: exit code 1 if false violation or false compliance occurs
    if summary.false_positive_violations > 0 or summary.false_positive_compliances > 0:
        print("[CRITICAL SAFETY ALERT] Benchmark detected false violation or false compliance!")
        return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="SANGYAN Evaluation Suite Runner")
    parser.add_argument("--suite", default="all", help="all, retrieval, assessment, adversarial, multilingual, temporal, cross-document")
    parser.add_argument("--category", default=None, help="Filter by specific CaseCategory")
    parser.add_argument("--difficulty", default=None, help="Filter by L1, L2, L3, L4, L5, L6")
    parser.add_argument("--visibility", default="PUBLIC", help="PUBLIC, HIDDEN, ALL")
    parser.add_argument("--case", default=None, help="Evaluate a single case by case_id")
    parser.add_argument("--model", default="sangyan-deterministic-v1", help="Model descriptor for audit")
    parser.add_argument("--output", default=None, help="File path to save JSON report")
    parser.add_argument("--run-label", default="7C-SEMANTIC-RETRIEVAL", help="Label for this benchmark run")

    args = parser.parse_args()

    out_p = Path(args.output) if args.output else None
    code = asyncio.run(
        run_evaluation_suite(
            suite=args.suite,
            category=args.category,
            difficulty=args.difficulty,
            visibility=args.visibility,
            case_id=args.case,
            model=args.model,
            output_path=out_p,
            run_label=args.run_label,
        )
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
