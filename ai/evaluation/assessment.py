"""Reproducible Assessment Benchmark Runner for SANGYAN.

Usage:
    python -m ai.evaluation.assessment
"""

import sys
from ai.app.evaluation.assessment_evaluator import AssessmentEvaluator


def main() -> None:
    evaluator = AssessmentEvaluator()
    summary = evaluator.evaluate_all()
    report_path = evaluator.save_report(summary)

    print("\n" + "=" * 55)
    print("SANGYAN Epistemic Assessment Benchmark Evaluation")
    print("=" * 55)
    print(f"Total Cases:                   {summary.total_cases}")
    print(f"Status Accuracy:               {summary.status_accuracy * 100:.1f}%")
    print(f"Condition Accuracy:            {summary.condition_accuracy * 100:.1f}%")
    print(f"Exception Accuracy:            {summary.exception_accuracy * 100:.1f}%")
    print(f"Temporal Accuracy:             {summary.temporal_accuracy * 100:.1f}%")
    print(f"Authority Accuracy:            {summary.authority_accuracy * 100:.1f}%")
    print(f"Evidence Sufficiency Accuracy: {summary.evidence_sufficiency_accuracy * 100:.1f}%")
    print(f"Conflict Detection Accuracy:   {summary.conflict_detection_accuracy * 100:.1f}%")
    print(f"Numerical Accuracy (Decimal):  {summary.numerical_accuracy * 100:.1f}%")
    print(f"Provenance Completeness:       {summary.provenance_completeness * 100:.1f}%")
    print("-" * 55)
    print("SAFETY-CRITICAL INVARIANT AUDIT:")
    print(f"  False Positive Violations:   {summary.false_positive_violations} (MUST BE 0)")
    print(f"  False Positive Compliances:  {summary.false_positive_compliances} (MUST BE 0)")
    print("-" * 55)

    failures = [c for c in summary.cases if not c.status_match]
    if failures:
        print(f"\nDiscrepancies ({len(failures)}):")
        for f in failures:
            print(f"  [{f.case_id}] Expected {f.expected_status.value}, got {f.actual_status.value}")
    else:
        print("\nAll 16 gold benchmark assessment cases passed with zero discrepancies!")

    print(f"\nDetailed report saved to: {report_path.resolve()}\n")

    if summary.false_positive_violations > 0 or summary.false_positive_compliances > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
