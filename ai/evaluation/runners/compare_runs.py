"""Benchmark Run Comparison and Regression Detection Engine for SANGYAN (Phase 7A).

Usage:
    python -m ai.evaluation.runners.compare_runs --baseline baseline.json --candidate candidate.json
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from ai.evaluation.corpus.models import BenchmarkSuiteReport


def format_delta(base: float, cand: float, is_percentage: bool = True) -> str:
    diff = cand - base
    if is_percentage:
        pp = diff * 100
        sign = "+" if pp > 0 else ""
        return f"{base * 100:.1f}% -> {cand * 100:.1f}%  ({sign}{pp:.1f}pp)"
    else:
        sign = "+" if diff > 0 else ""
        return f"{base:.3f} -> {cand:.3f}  ({sign}{diff:.3f})"


def compare_runs(baseline_file: Path, candidate_file: Path) -> int:
    """Compare baseline and candidate benchmark reports and print regression audit."""
    if not baseline_file.exists():
        print(f"[ERROR] Baseline report file not found: {baseline_file}")
        return 1
    if not candidate_file.exists():
        print(f"[ERROR] Candidate report file not found: {candidate_file}")
        return 1

    with open(baseline_file, encoding="utf-8") as f:
        base_data = json.load(f)
    with open(candidate_file, encoding="utf-8") as f:
        cand_data = json.load(f)

    base = BenchmarkSuiteReport(**base_data)
    cand = BenchmarkSuiteReport(**cand_data)

    print("\n" + "=" * 65)
    print("SANGYAN Benchmark Regression Comparison")
    print(f"Baseline:  {baseline_file.name} (executed: {base.executed_at.strftime('%Y-%m-%d %H:%M')})")
    print(f"Candidate: {candidate_file.name} (executed: {cand.executed_at.strftime('%Y-%m-%d %H:%M')})")
    print("=" * 65)

    print(f"Overall Accuracy:            {format_delta(base.accuracy, cand.accuracy)}")
    print(f"Fact Extraction Accuracy:    {format_delta(base.fact_accuracy, cand.fact_accuracy)}")
    print(f"Unknown Integrity:           {format_delta(base.fact_unknown_accuracy, cand.fact_unknown_accuracy)}")
    print(f"Issue Identification:        {format_delta(base.issue_recall, cand.issue_recall)}")
    print(f"Retrieval Recall@5:          {format_delta(base.retrieval_recall_at_5, cand.retrieval_recall_at_5)}")
    print(f"Retrieval Recall@10:         {format_delta(base.retrieval_recall_at_10, cand.retrieval_recall_at_10)}")
    print(f"Retrieval MRR:               {format_delta(base.retrieval_mrr, cand.retrieval_mrr, is_percentage=False)}")
    print(f"Retrieval Required Recall:   {format_delta(base.retrieval_required_recall, cand.retrieval_required_recall)}")
    print(f"Temporal Accuracy:           {format_delta(base.temporal_correctness, cand.temporal_correctness)}")
    print(f"Contradiction Detection:     {format_delta(base.evidence_contradiction_accuracy, cand.evidence_contradiction_accuracy)}")
    print(f"Assessment Status Accuracy:  {format_delta(base.assessment_status_accuracy, cand.assessment_status_accuracy)}")
    print(f"Condition Accuracy:          {format_delta(base.condition_accuracy, cand.condition_accuracy)}")
    print(f"Numerical Accuracy:          {format_delta(base.numerical_accuracy, cand.numerical_accuracy)}")
    print(f"Clarification Precision:     {format_delta(base.clarification_precision, cand.clarification_precision)}")

    print("-" * 65)
    print("SAFETY-CRITICAL COMPARISON:")
    fv_diff = cand.false_positive_violations - base.false_positive_violations
    fc_diff = cand.false_positive_compliances - base.false_positive_compliances

    fv_status = "REGRESSION" if fv_diff > 0 else ("IMPROVEMENT" if fv_diff < 0 else "UNCHANGED")
    fc_status = "REGRESSION" if fc_diff > 0 else ("IMPROVEMENT" if fc_diff < 0 else "UNCHANGED")

    print(f"  False Violations:   {base.false_positive_violations} -> {cand.false_positive_violations}  [{fv_status}]")
    print(f"  False Compliances:  {base.false_positive_compliances} -> {cand.false_positive_compliances}  [{fc_status}]")

    # Case-level regression analysis
    base_case_map = {c.case_id: c for c in base.cases}
    cand_case_map = {c.case_id: c for c in cand.cases}

    common_cases = set(base_case_map.keys()).intersection(cand_case_map.keys())

    regressed_cases = []
    fixed_cases = []

    for cid in sorted(common_cases):
        b_pass = base_case_map[cid].overall_passed
        c_pass = cand_case_map[cid].overall_passed

        if b_pass and not c_pass:
            regressed_cases.append((cid, cand_case_map[cid].failure_class))
        elif not b_pass and c_pass:
            fixed_cases.append(cid)

    print("-" * 65)
    print(f"CASE-LEVEL DELTA: Fixed: {len(fixed_cases)} | Regressed: {len(regressed_cases)}")

    if fixed_cases:
        print("\n  Fixed Cases:")
        for cid in fixed_cases:
            print(f"    + {cid}")

    if regressed_cases:
        print("\n  [REGRESSION ALERT] Regressed Cases:")
        for cid, f_class in regressed_cases:
            print(f"    - {cid} (Failure Class: {f_class})")

    print("=" * 65 + "\n")

    # Return exit code 1 if safety regressed or regressions exceed fixes
    if cand.false_positive_violations > 0 or cand.false_positive_compliances > 0 or len(regressed_cases) > 0:
        return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="SANGYAN Benchmark Run Comparison")
    parser.add_argument("--baseline", required=True, help="Path to baseline JSON report")
    parser.add_argument("--candidate", required=True, help="Path to candidate JSON report")

    args = parser.parse_args()
    code = compare_runs(Path(args.baseline), Path(args.candidate))
    sys.exit(code)


if __name__ == "__main__":
    main()
