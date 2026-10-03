import json
from pathlib import Path

path = Path("ai/corpus/retrieval_benchmark_report.json")
if not path.exists():
    path = Path("corpus/retrieval_benchmark_report.json")

with open(path, "r", encoding="utf-8") as f:
    d = json.load(f)

print(f"Total Cases: {d['total_cases']}, Failures: {d['metrics']['total_failures']}")
print("=" * 60)
for c in d["cases"]:
    if c.get("failure_classification"):
        print(f"Case ID:        {c['case_id']}")
        print(f"Description:    {c['description']}")
        print(f"Classification: {c['failure_classification']}")
        print(f"Expected IDs:   {c['expected_provision_ids']}")
        print(f"Retrieved Top3: {c['retrieved_provision_ids'][:3]}")
        print(f"Recall@5:       {c['recall_at_5']}")
        print(f"Recall@10:      {c['recall_at_10']}")
        print(f"MRR:            {c['reciprocal_rank']}")
        print("-" * 60)
