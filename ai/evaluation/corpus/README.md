# SANGYAN Phase 7A: Adversarial Evaluation & Grievance Corpus

## 1. Overview
The SANGYAN Evaluation Framework provides an automated, machine-readable harness designed to measure the epistemic intelligence of the legal-evidentiary pipeline.

It tests:
- **Fact Extraction**: Accuracy of extracted typed fields and enforcement of epistemic unknowns.
- **Issue Identification**: Precision and recall of primary and secondary legal issues.
- **Evidence Resolution**: Contradiction detection, claim linkage, and policy precedence.
- **Provision Retrieval**: Recall@1/5/10/20, MRR, nDCG@10, and required provision recall.
- **Temporal Reasoning**: Historical circular regime vs superseded circular selection.
- **Cross-Document Reasoning**: Multi-authority joint conditions (SEBI + CDSL/NSDL + Broker tariff).
- **Compound Financial Arithmetic**: Exact Decimal reconciliation across taxes, fees, and charges.
- **Assessment**: Deterministic condition evaluation, zero false violation / zero false compliance.
- **Clarification**: Precision, recall, and unnecessary question suppression.
- **Grounding**: Citation verification and detection of unsupported assertions.

## 2. Directory Structure
```text
ai/evaluation/
├── corpus/               # Data contracts, loader, validator, taxonomy
├── cases/                # Benchmark cases across 10 distinct categories
│   ├── basic/            # Straightforward complaints (L1)
│   ├── ambiguous/        # Vague language / missing essential fields (L2)
│   ├── contradictory/    # Conflicting statements vs documents (L3)
│   ├── temporal/         # Historical amendment regimes (L5)
│   ├── cross_document/   # Regulatory + depository + broker rules (L4)
│   ├── compound_financial/ # Complex arithmetic breakdown (L5)
│   ├── regulatory_gap/   # Uncovered or unregistered activities (L2/L3)
│   ├── multilingual/     # Hindi / Hinglish grievances (L1/L2)
│   ├── adversarial/      # Injections, misleading docs, near-matches (L6)
│   └── multi_turn/       # Multi-turn conversational evolution
├── evaluators/           # Stage-specific epistemic verification modules
├── runners/              # CLI evaluation and regression runners
└── reports/              # JSON and summary evaluation output
```

## 3. Epistemic Principles
1. **Plausibility ≠ Correctness**: A superficial or well-formatted answer is marked incorrect if the underlying regulatory condition, provision, or calculation is wrong.
2. **Negative Invariants**: Hallucinating missing facts when none were stated is penalized via `ExpectedUnknown`.
3. **No Synthetic Law**: Synthetic grievances are allowed; synthetic regulatory rules are forbidden. All provisions must resolve to PostgreSQL records or be marked `is_blocked_by_corpus_gap`.
4. **No Single Magic Score**: Metrics are tracked at stage-level and partitioned by difficulty (L1–L6).
