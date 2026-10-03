"""Execute SANGYAN Retrieval Evaluation over 25 Gold Benchmark Cases.

Outputs formatted benchmark report and writes machine-readable JSON:
`ai/corpus/retrieval_benchmark_report.json`
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

from ai.app.config.settings import settings
from ai.app.db.session import get_async_session
from ai.app.evaluation.benchmark_cases import GOLD_BENCHMARK_CASES
from ai.app.evaluation.retrieval_evaluator import RetrievalEvaluator
from ai.app.retrieval.embedding_provider import OllamaEmbeddingProvider
from ai.app.retrieval.retriever import DefaultProvisionRetriever


async def main() -> None:
    print("=" * 70)
    print("SANGYAN Provision Retrieval Benchmark Evaluation")
    print("=" * 70)

    db_url = settings.database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL is not set.")
        return

    provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url or "http://localhost:11434",
        model_id="nomic-embed-text",
        model_version="v1.5",
        dimension=768,
    )
    retriever = DefaultProvisionRetriever(embedding_provider=provider)
    evaluator = RetrievalEvaluator(retriever=retriever)

    print(f"[BENCHMARK] Executing {len(GOLD_BENCHMARK_CASES)} gold benchmark cases...")
    start_time = time.perf_counter()

    async with get_async_session() as session:
        summary = await evaluator.evaluate_all(cases=GOLD_BENCHMARK_CASES, session=session)

    duration = time.perf_counter() - start_time

    # Print Formatted Report
    print("\n" + "=" * 70)
    print("SANGYAN Retrieval Evaluation Summary")
    print("=" * 70)
    print(f"Total Benchmark Cases:      {summary.total_cases}")
    print(f"Total Execution Time:       {duration:.2f}s (avg {summary.mean_latency_ms:.1f}ms/case)")
    print("-" * 70)
    print("INFORMATION RETRIEVAL METRICS:")
    print(f"  Recall@5:                 {summary.mean_recall_at_5 * 100:.1f}%")
    print(f"  Recall@10:                {summary.mean_recall_at_10 * 100:.1f}%")
    print(f"  Recall@20:                {summary.mean_recall_at_20 * 100:.1f}%")
    print(f"  Precision@5:              {summary.mean_precision_at_5 * 100:.1f}%")
    print(f"  Precision@10:             {summary.mean_precision_at_10 * 100:.1f}%")
    print(f"  MRR (Mean Recip. Rank):   {summary.mean_reciprocal_rank:.4f}")
    print("-" * 70)
    print("DOMAIN & EPISTEMIC CORRECTNESS:")
    print(f"  Authority Correctness:    {summary.authority_correctness * 100:.1f}%")
    print(f"  Organisation Correctness: {summary.organisation_correctness * 100:.1f}%")
    print(f"  Temporal Correctness:     {summary.temporal_correctness * 100:.1f}%")
    print(f"  Citation Correctness:     {summary.citation_correctness * 100:.1f}%")
    print(f"  Total Retrieval Failures: {summary.total_failures}")
    print("=" * 70)

    # Save JSON report
    report_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": summary.total_cases,
        "metrics": {
            "recall_at_5": summary.mean_recall_at_5,
            "recall_at_10": summary.mean_recall_at_10,
            "recall_at_20": summary.mean_recall_at_20,
            "precision_at_5": summary.mean_precision_at_5,
            "precision_at_10": summary.mean_precision_at_10,
            "mrr": summary.mean_reciprocal_rank,
            "authority_correctness": summary.authority_correctness,
            "organisation_correctness": summary.organisation_correctness,
            "temporal_correctness": summary.temporal_correctness,
            "citation_correctness": summary.citation_correctness,
            "total_failures": summary.total_failures,
            "mean_latency_ms": summary.mean_latency_ms,
        },
        "cases": [c.model_dump() for c in summary.cases],
    }

    out_path = Path(__file__).resolve().parent.parent / "corpus" / "retrieval_benchmark_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\n[REPORT] Saved machine-readable benchmark report at: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
