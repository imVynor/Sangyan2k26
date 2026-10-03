"""Evaluation runner for SANGYAN AI model benchmarking.

Runs standardized evaluation test cases across registered models and records:
- Success/failure
- Latency (ms)
- Schema validity (CaseUnderstanding)
- Epistemic integrity (claims vs facts, unknowns, hypotheses)
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
runner_dir = Path(__file__).resolve().parent
ai_root = runner_dir.parent.parent
project_root = ai_root.parent
for p in [str(ai_root), str(project_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from ai.app.models.ollama import OllamaProvider
from ai.app.models.registry import get_model, get_model_config
from ai.app.models.schemas import CaseUnderstanding, Message
from ai.app.utils.json_utils import JSONParsingError, SchemaValidationError
from ai.evals.runners.eval_schema import EvaluationCase, EvaluationReport, EvaluationResult


SCHEMA_MAP = {
    "CaseUnderstanding": CaseUnderstanding,
}


def load_benchmark_cases(cases_file: Path | str | None = None) -> list[EvaluationCase]:
    """Load benchmark cases from JSON file."""
    if cases_file is None:
        cases_file = ai_root / "evals" / "cases" / "initial_benchmark.json"
    path = Path(cases_file)
    if not path.exists():
        raise FileNotFoundError(f"Benchmark file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [EvaluationCase.model_validate(item) for item in data]


async def evaluate_single_case(
    provider: OllamaProvider,
    case: EvaluationCase,
    temperature: float = 0.0,
) -> EvaluationResult:
    """Run an individual evaluation case on a model provider."""
    messages = [
        Message(role="system", content=case.system_prompt),
        Message(role="user", content=case.user_prompt),
    ]

    schema_class = SCHEMA_MAP.get(case.expected_schema) if case.expected_schema else None

    start_time = time.perf_counter()
    output_content = ""
    parsed_dict: dict[str, Any] | None = None
    validation_error: str | None = None
    success = False
    notes: list[str] = []

    try:
        if schema_class is not None:
            # Structured generation path
            validated_obj = await provider.generate_structured(
                messages=messages,
                response_model=schema_class,
                temperature=temperature,
            )
            success = True
            parsed_dict = validated_obj.model_dump()
            output_content = json.dumps(parsed_dict, indent=2, ensure_ascii=False)
            notes.append(f"Successfully validated against {schema_class.__name__}")

            # Specific epistemic checks
            if isinstance(validated_obj, CaseUnderstanding):
                notes.append(
                    f"Parsed: {len(validated_obj.entities)} entity(s), "
                    f"{len(validated_obj.facts)} fact(s), "
                    f"{len(validated_obj.claims)} claim(s), "
                    f"{len(validated_obj.unknowns)} unknown(s), "
                    f"{len(validated_obj.hypotheses)} hypothesis(es)"
                )
        else:
            # Plain generation path
            response = await provider.generate(
                messages=messages,
                temperature=temperature,
            )
            output_content = response.content
            success = bool(response.content.strip())
            notes.append("Plain text generation succeeded")

    except (JSONParsingError, SchemaValidationError) as val_err:
        success = False
        validation_error = str(val_err)
        notes.append(f"Validation failure: {val_err}")
    except Exception as exc:
        success = False
        validation_error = f"Execution exception: {type(exc).__name__}: {exc}"
        notes.append(f"Execution error: {exc}")

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return EvaluationResult(
        case_id=case.id,
        model=provider.model_name,
        success=success,
        latency_ms=elapsed_ms,
        output=output_content,
        parsed_output=parsed_dict,
        validation_error=validation_error,
        notes=" | ".join(notes),
    )


async def run_evaluation(
    model_aliases: list[str],
    cases_file: Path | str | None = None,
    save_results: bool = True,
    temperature: float = 0.0,
) -> EvaluationReport:
    """Run full evaluation suite across multiple model aliases."""
    cases = load_benchmark_cases(cases_file)
    print(f"\nLoaded {len(cases)} benchmark cases from {cases_file or 'initial_benchmark.json'}")

    all_results: list[EvaluationResult] = []
    summary_by_model: dict[str, dict[str, Any]] = {}

    for alias in model_aliases:
        config = get_model_config(alias)
        model_name = config["model"]
        print(f"\n==================================================")
        print(f"Evaluating Model: {model_name} (Alias: {alias})")
        print(f"==================================================")

        provider = get_model(alias)
        model_results: list[EvaluationResult] = []

        try:
            for idx, case in enumerate(cases, 1):
                print(f"  [{idx:02d}/{len(cases):02d}] Running '{case.id}' ({case.category})...", end=" ", flush=True)
                result = await evaluate_single_case(provider, case, temperature=temperature)
                model_results.append(result)
                all_results.append(result)

                status_str = "PASS" if result.success else "FAIL"
                print(f"[{status_str}] ({result.latency_ms:.0f}ms)")
                if not result.success:
                    print(f"         Reason: {result.validation_error}")
        finally:
            if hasattr(provider, "close"):
                await provider.close()

        # Compute summary metrics
        passed = sum(1 for r in model_results if r.success)
        total = len(model_results)
        avg_latency = (
            sum(r.latency_ms for r in model_results) / total if total > 0 else 0.0
        )
        summary_by_model[model_name] = {
            "alias": alias,
            "total_cases": total,
            "passed": passed,
            "failed": total - passed,
            "accuracy_pct": round((passed / total) * 100, 1) if total > 0 else 0.0,
            "avg_latency_ms": round(avg_latency, 1),
        }

    report = EvaluationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        models_evaluated=[get_model_config(a)["model"] for a in model_aliases],
        total_cases=len(cases),
        summary_by_model=summary_by_model,
        results=all_results,
    )

    if save_results:
        results_dir = ai_root / "evals" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_file = results_dir / f"eval_report_{ts_slug}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        print(f"\nSaved evaluation report to: {report_file}")

    return report


def main() -> None:
    """CLI entrypoint for evaluation runner."""
    import argparse

    parser = argparse.ArgumentParser(description="SANGYAN Model Evaluation Runner")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gemma_fast"],
        help="List of model aliases to evaluate (e.g. gemma_fast, qwen_reasoning)",
    )
    parser.add_argument(
        "--cases",
        type=str,
        default=None,
        help="Path to evaluation cases JSON file",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Temperature for generation (default: 0.0)",
    )

    args = parser.parse_args()

    report = asyncio.run(
        run_evaluation(
            model_aliases=args.models,
            cases_file=args.cases,
            temperature=args.temperature,
        )
    )

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    for model, summary in report.summary_by_model.items():
        print(
            f"Model: {model:<18} | Pass: {summary['passed']}/{summary['total_cases']} "
            f"({summary['accuracy_pct']}%) | Avg Latency: {summary['avg_latency_ms']}ms"
        )
    print("=" * 60)


if __name__ == "__main__":
    main()
