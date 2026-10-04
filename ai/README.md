# SANGYAN AI Backend — Core Architecture & Knowledge Engine

The AI backend for the **SANGYAN Investor Grievance Platform** is an epistemic reasoning system built for investor grievances in the Indian financial markets (SEBI, CDSL, NSDL, NSE, BSE, Zerodha, Groww, Angel One, Upstox, ICICI Direct).

---

## 🏛️ Foundational Architectural Principle

> **SANGYAN is NOT a generic chatbot and NOT a generic RAG wrapper.**

The system maintains strict architectural boundaries between empirical fact extraction, regulatory provision retrieval, deterministic rule evaluation, and user explanation generation:

```text
                        INVESTOR INPUT (Narrative / Docs)
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │   Fact Extraction Service │  (Phase 4)
                         │   - Verbatim Source Spans │
                         │   - Epistemic Status      │
                         │   - Decimal Financials    │
                         └───────────────────────────┘
                                       │
                                       ▼
                            Evidence Proposals &
                            Candidate Case Facts
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │  Evidence Manager Boundary│  (Phase 3)
                         │  - Reconciles Conflicts   │
                         │  - CaseState Immutability │
                         └───────────────────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │  Hybrid Retrieval Service │  (Phase 2)
                         │  - BM25 + Dense pgvector  │
                         │  - Temporal Filter Engine │
                         └───────────────────────────┘
                                       │
                                       ▼
                              Retrieved Provisions
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │  Epistemic Assessment     │  (Phase 3)
                         │  - 3-Valued Logic (3VL)   │
                         │  - Condition/Exception    │
                         │  - Deterministic Status   │
                         └───────────────────────────┘
                                       │
                                       ▼
                               AssessmentResult
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │  Auditable Generation     │  (Phase 4)
                         │  - Grounded Explanations  │
                         │  - Citation Validator     │
                         │  - Escalation Action Path │
                         └───────────────────────────┘
                                       │
                                       ▼
                           Validated Citizen Output
```

---

## 🏗️ Architectural Phase Breakdown

### Phase 0: Model Abstraction & Evaluation Infrastructure
- Provider-agnostic LLM interface (`LLMProvider`, `OllamaProvider`, `BaseModel`).
- Structured Pydantic parsing with automated schema validation.
- Evaluation harness for tracking latency, token usage, and format compliance.

### Phase 1A: Canonical Knowledge Domain & Contracts
- Core domain contracts in `ai/app/knowledge/`:
  - `SourceClass`: `REGULATORY`, `ORGANISATION_POLICY`, `ORGANISATION_FAQ`, etc.
  - `TemporalScope`: Effective dates, termination dates, and `SupersededStatus`.
  - `Provenance`: Verbatim URL, content SHA-256 fingerprint, and retrieval timestamp.
  - `Provision`: Atomic rules, obligations, entitlements, timelines, fees, and exceptions.

### Phase 1B: Deterministic Ingestion & Fingerprinting
- Deterministic extraction for HTML and PDF documents with zero synthetic padding.
- Exact structural segmentation into `DocumentSection` hierarchies.
- SHA-256 deduplication and canonical document identification.

### Phase 1C-A: PostgreSQL Persistence & Alembic Migrations
- Production-grade relational storage with SQLAlchemy Declarative models.
- Atomic transactional repository (`PostgresKnowledgeRepository`) with offline `InMemoryKnowledgeRepository`.
- Bi-directional schema mappers maintaining domain invariants.

### Phase 1C-B: Source Acquisition & Authority Graph
- Domain routing and authority hierarchy (`SEBI > CDSL/NSDL > Brokers`).
- Bounded discovery and crawl manifest tracking official circulars and tariff schedules.
- Populated authoritative corpus with 16 real regulatory documents and 256 sections.

### Phase 2: Hybrid Retrieval & Semantic Provision Indexing
- 1,515 atomic provisions extracted with exact source substring coordinates.
- Hybrid provision-level retriever combining:
  - BM25 keyword scoring over canonical text.
  - Dense pgvector cosine embeddings (768-dim `nomic-embed-text`).
  - Strict temporal filtering (`TemporalApplicabilityEngine`) resolving historical circular validity.
- Authority filtering preventing broker policies from overriding regulatory circulars.

### Phase 3: Epistemic Assessment & Deterministic Evaluation
- Epistemic determination engine applying three-valued logic (True / False / Unknown).
- Condition and exception clause evaluators (`FeeEvaluator`, `TimelineEvaluator`).
- Dedicated `EvidenceManager` supporting multiple evidentiary layers (`USER_ASSERTED`, `DOCUMENT_ASSERTED`, `SYSTEM_RECORD`).
- Strict safety invariants:
  - Absence of a documented violation NEVER implies compliance.
  - User assertions NEVER alter statutory conditions without documentary proof.

### Phase 4: Evidentiary Fact Extraction & Auditable Generation
- **Fact Extraction Service** (`ai/app/extraction/`):
  - Preserves exact source spans: `input_text[start:end] == span_text`.
  - Normalizes currencies to `Decimal` (`INR`) and handles compound GST tariffs (`₹13.50 + 18% = ₹15.93`).
  - Enforces reference date grounding for relative dates (`yesterday`, `last Friday`).
  - Multilingual support for English, Hindi (Devanagari), and Hinglish with language-independent canonical facts.
- **Auditable Generation Service** (`ai/app/generation/`):
  - Strictly read-only: consumes `AssessmentResult` and retrieved provisions.
  - Validates all statutory citations against retrieved context; rejects hallucinations (`INVALID_CITATION`).
  - Verifies factual grounding; rejects unsupported claims (`UNSUPPORTED_CLAIM`).
  - Formats actionable next steps with official grievance escalation routes (SCORES 2.0, SMART ODR).
- After deterministic generation, an optional small Ollama model (`gemma3:1b` by default) rewrites only the citizen-facing summary for clarity. Assessment status, evidence, citations, and follow-up questions remain authoritative and unchanged. The rewrite has a 2.5-second timeout and falls back to the deterministic summary if Ollama or the model is unavailable. Configure with `RESPONSE_MODEL`, `RESPONSE_GENERATION_TIMEOUT`, and `OLLAMA_BASE_URL`; install the default model with `ollama pull gemma3:1b`.

---

## 📁 AI Backend Structure

```text
ai/
├── app/
│   ├── assessment/          # Epistemic assessment engine & rule evaluators
│   ├── config/              # Pydantic Settings & environment loader
│   ├── corpus/              # Authoritative corpus files & benchmark reports
│   ├── db/                  # PostgreSQL ORM models, session & repository
│   ├── extraction/          # Fact extraction, normalizers, OCR & case integrator
│   ├── generation/          # Grounded generator, citation renderer & validator
│   ├── ingestion/           # Deterministic HTML/PDF parsers & pipeline
│   ├── knowledge/           # Canonical models (provisions, temporal, provenance)
│   ├── models/              # LLM provider abstractions & registries
│   └── retrieval/           # Hybrid retriever, pgvector indexing & domain router
├── evaluation/              # Benchmark runners (retrieval, assessment, end-to-end)
├── scripts/                 # Corpus extraction, DB seeding & CLI utilities
└── tests/                   # 231 unit, integration, and regression test suites
```

---

## 🧪 Testing & Verification

### Running the Full Regression Test Suite
All 231 tests pass cleanly:
```bash
python -m pytest ai/tests -q
```

### Running Layer-Specific Tests
```bash
# Phase 4 Fact Extraction & Generation
python -m pytest ai/tests/test_extraction.py ai/tests/test_generation.py -v

# Phase 3 Epistemic Assessment & Evidence Manager
python -m pytest ai/tests/test_assessment.py -v

# Phase 2 Provision Extraction & Vector Index
python -m pytest ai/tests/test_provision_extraction.py ai/tests/test_vector_index.py -v
```

---

## 📊 Evaluation Benchmarks

SANGYAN includes three automated benchmark suites:

### 1. End-to-End Gold Cases Benchmark (Phase 4)
Executes 20 full-lifecycle dispute scenarios from natural complaint to grounded response:
```bash
python -m ai.evaluation.end_to_end
```
- Fact Extraction Accuracy: **100.0%**
- Numeric Accuracy (`Decimal`): **100.0%**
- Date Accuracy: **100.0%**
- Entity Accuracy: **100.0%**
- Citation Correctness: **100.0%**
- Assessment Preservation: **100.0%**
- Unsupported Claim Rate: **0.0%**
- Multilingual Accuracy (Hindi/Hinglish): **100.0%**
- Generation Validation Pass Rate: **100.0%**

### 2. Epistemic Assessment Benchmark (Phase 3)
Evaluates 16 statutory and broker-deviation cases:
```bash
python -m ai.evaluation.assessment
```
- Status Accuracy: **100.0%**
- False Positive Violations: **0**
- False Positive Compliances: **0**

### 3. Hybrid Provision Retrieval Benchmark (Phase 2)
Evaluates retrieval across 25 gold queries against PostgreSQL + pgvector:
```bash
python -m ai.evaluation.retrieval
```
- Authority Correctness: **100.0%**
- Organisation Correctness: **100.0%**
- Citation Correctness: **100.0%**
- MRR: **0.7111**
