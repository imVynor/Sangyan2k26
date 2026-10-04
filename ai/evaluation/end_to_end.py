"""Reproducible End-to-End Benchmark Runner for SANGYAN Phase 4.

Usage:
    python -m ai.evaluation.end_to_end
"""

import sys
from ai.app.evaluation.end_to_end_evaluator import EndToEndEvaluator


def main() -> None:
    evaluator = EndToEndEvaluator()
    summary = evaluator.evaluate_all()
    report_path = evaluator.save_report(summary)

    print("\n" + "=" * 60)
    print("SANGYAN Phase 4 End-to-End Pipeline Benchmark Evaluation")
    print("=" * 60)
    print(f"Total Cases:                   {summary.total_cases}")
    print(f"Fact Extraction Accuracy:      {summary.fact_extraction_accuracy * 100:.1f}%")
    print(f"Numeric Accuracy (Decimal):    {summary.numeric_accuracy * 100:.1f}%")
    print(f"Date Accuracy:                 {summary.date_accuracy * 100:.1f}%")
    print(f"Entity Accuracy:               {summary.entity_accuracy * 100:.1f}%")
    print(f"Citation Correctness:          {summary.citation_correctness * 100:.1f}%")
    print(f"Assessment Preservation:       {summary.assessment_preservation * 100:.1f}%")
    print(f"Unsupported Claim Rate:        {summary.unsupported_claim_rate * 100:.1f}% (TARGET: 0.0%)")
    print(f"Multilingual Accuracy (HI/HIN):{summary.multilingual_accuracy * 100:.1f}%")
    print(f"Generation Validation Pass:    {summary.validation_pass_rate * 100:.1f}%")
    print("-" * 60)

    failures = [c for c in summary.cases if not c.status_preserved or not c.extraction_match]
    if failures:
        print(f"\nDiscrepancies ({len(failures)}):")
        for f in failures:
            print(f"  [{f.case_id}] Status: {f.actual_status.value} (Expected: {f.expected_status.value}), ExtMatch: {f.extraction_match}")
    else:
        print("\nAll 20 end-to-end gold benchmark cases passed with zero discrepancies!")

    print(f"\nDetailed report saved to: {report_path.resolve()}\n")

    if summary.unsupported_claim_rate > 0.0:
        sys.exit(1)


if __name__ == "__main__":
    main()
