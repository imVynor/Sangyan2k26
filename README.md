# SANGYAN (संज्ञान) — Regulatory Grievance Reasoning & Investor Protection Platform

An end-to-end investor grievance reasoning and regulatory compliance platform for the Indian financial ecosystem (SEBI, CDSL, NSDL, NSE, BSE, and registered brokers).

SANGYAN pairs a modern **React 19 + Node.js/Express MERN** web application with a specialized **Python Epistemic AI Backend** designed around deterministic regulatory evaluation, exact provenance, and auditable, hallucination-free explanation generation.

---

## 🏛️ System Architecture

```text
                                 CITIZEN / INVESTOR
                                          │
                        ┌─────────────────┴─────────────────┐
                        ▼                                   ▼
             React 19 SPA (Vite)                   Uploaded Documents
         (English / Hindi / Hinglish)          (Contract Notes, PDF, OCR)
                        │                                   │
                        └─────────────────┬─────────────────┘
                                          ▼
                               Node.js Express API
                         (MERN Web & Orchestration Layer)
                                          │
                                          ▼
                     ╔═════════════════════════════════════╗
                     ║    SANGYAN AI REASONING BACKEND     ║
                     ╚═════════════════════════════════════╝
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   1. Evidentiary Fact Extractor │
                         │      (Exact Spans, Decimals)    │
                         └─────────────────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │  2. Case Integrator / Evidence  │
                         │    (No Direct State Mutation)   │
                         └─────────────────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │  3. Hybrid Provision Retrieval  │
                         │     (BM25 + Dense + Temporal)   │
                         └─────────────────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │  4. Deterministic Assessment    │
                         │    (Rules, Exceptions, 3VL)     │
                         └─────────────────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │  5. Auditable Response Gen.     │
                         │    (Validated Statutory Cit.)   │
                         └─────────────────────────────────┘
```

---

## 🌟 Core Architecture Principles

1. **Deterministic Regulatory Truth**:
   The LLM is **never** the source of regulatory law. Regulatory rules and tariff ceilings are acquired from official sources (SEBI, CDSL, NSE, BSE), segmented into atomic provisions, and evaluated using three-valued logic (True / False / Unknown).
2. **Separation of Extraction, Assessment, and Generation**:
   No single "reasoning LLM" performs fact extraction, legal judgment, and generation at once. Assessment is mathematical and deterministic; generation is read-only and citation-grounded.
3. **Exact Source-Span Preservation**:
   Every extracted fact preserves verbatim text slices and character offsets (`source_start`, `source_end`), guaranteeing complete provenance down to the exact paragraph or PDF coordinate.
4. **Epistemic Classification**:
   Facts are segregated into `USER_ASSERTED`, `DOCUMENT_ASSERTED`, and `DERIVED`. Unverified user claims (e.g. *"I think Zerodha overcharged me"*) are captured as user beliefs—never legal violations.
5. **Zero Floating-Point Financials**:
   All monetary amounts and percentages use `Decimal` with strict currency tags (`INR`) and automatic compound GST breakdown (`13.50 + 18% = 15.93`).
6. **Strict Citation Validation**:
   Every generated statutory claim is cross-checked against retrieved provisions before rendering to the citizen. Hallucinated circulars or unsupported factual claims are rejected (`INVALID_CITATION` / `UNSUPPORTED_CLAIM`).

---

## 📁 Repository Structure

```text
Sungyan/
├── package.json             # Root monorepo script runner (concurrently)
├── README.md                # System overview and quickstart
├── .gitignore               # Multi-stack gitignore (Node.js + Python + Secrets)
│
├── frontend/                # React 19 + Vite SPA
│   ├── src/
│   │   ├── components/      # UI components (Inter + Outfit typography, Glassmorphism)
│   │   ├── services/api.js  # REST API client with mock connection fallback
│   │   └── App.jsx
│   └── vite.config.js       # Vite reverse proxy for /api
│
├── backend/                 # Node.js + Express REST API
│   ├── src/
│   │   ├── controllers/     # Dual-mode controllers (MongoDB + In-memory mock)
│   │   ├── models/          # Mongoose grievance and item schemas
│   │   └── server.js        # Express application entry
│   └── package.json
│
└── ai/                      # SANGYAN Python AI Engine & Epistemic Core
    ├── app/
    │   ├── assessment/      # Epistemic assessment engine & rule evaluators (Phase 3)
    │   ├── corpus/          # Authoritative documents, sections & provisions (Phase 1C-B)
    │   ├── db/              # PostgreSQL + pgvector persistence repository (Phase 1C-A)
    │   ├── extraction/      # Fact extraction, normalizer & document boundary (Phase 4)
    │   ├── generation/      # Citation renderer & auditable response generator (Phase 4)
    │   ├── ingestion/       # Deterministic HTML/PDF ingestion & fingerprinting (Phase 1B)
    │   ├── knowledge/       # Canonical domain models, provenance & temporal scope (Phase 1A)
    │   ├── models/          # LLM & Embedding provider abstractions (Phase 0)
    │   └── retrieval/       # Hybrid provision retriever (BM25 + Dense pgvector) (Phase 2)
    ├── evaluation/          # CLI evaluation runners (retrieval, assessment, end-to-end)
    ├── scripts/             # Data migration, corpus acquisition & benchmark scripts
    └── tests/               # 231 unit, integration, and property test suites
```

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** (v18+) & **npm**
- **Python** (v3.11+)
- **PostgreSQL** (with `pgvector` extension for semantic retrieval)
- *(Optional)* **Ollama** running `nomic-embed-text`

---

### 1. Web Portal Setup (MERN)

Install dependencies across the monorepo:
```bash
npm run install:all
```

Start both Express backend (`localhost:5000`) and Vite React frontend (`localhost:5173`) concurrently:
```bash
npm run dev
```

*Note: The backend features an automatic mock fallback. If MongoDB is not running locally, it defaults seamlessly to an in-memory data store.*

---

### 2. Python AI Engine Setup

Navigate to the `ai/` directory and configure the environment:
```bash
cd ai
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

Configure your local `.env` file in the root or `ai/`:
```ini
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/ai_knowledge
OLLAMA_BASE_URL=http://localhost:11434
```

---

### 3. Running AI Tests & Regression Suite

Run the full pytest suite (231 tests covering all phases):
```bash
python -m pytest ai/tests -q
```

Test specific architectural layers:
```bash
# Evidentiary Fact Extraction & Generation (Phase 4)
python -m pytest ai/tests/test_extraction.py ai/tests/test_generation.py -v

# Epistemic Assessment & Rule Engine (Phase 3)
python -m pytest ai/tests/test_assessment.py -v

# Hybrid Retrieval & pgvector Indexing (Phase 2)
python -m pytest ai/tests/test_hybrid_retriever.py -v
```

---

### 4. Running Verification Benchmarks

SANGYAN includes three automated benchmark suites:

1. **End-to-End Gold Cases Benchmark (Phase 4)**:
   ```bash
   python -m ai.evaluation.end_to_end
   ```
   Evaluates 20 full-lifecycle dispute cases (fact extraction, numeric precision, date parsing, citation grounding, multilingual Hindi/Hinglish complaints, and 0.0% unsupported claims).

2. **Epistemic Assessment Benchmark (Phase 3)**:
   ```bash
   python -m ai.evaluation.assessment
   ```
   Evaluates 16 statutory and broker-deviation cases with three-valued logic and safety invariant audits.

3. **Hybrid Provision Retrieval Benchmark (Phase 2)**:
   ```bash
   python -m ai.evaluation.retrieval
   ```
   Evaluates MRR, Recall@k, and authority correctness across the acquired regulatory corpus.

---

## 🛡️ License

Private repository developed for the SANGYAN grievance reasoning initiative.
