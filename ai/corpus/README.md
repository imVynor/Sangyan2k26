# SANGYAN Knowledge Corpus Manifest System

## Overview

The **Corpus Manifest** is the controlled, reproducible input specification for SANGYAN's knowledge acquisition and ingestion engine.

It explicitly declares the external regulatory and market intermediary documents that SANGYAN is permitted and required to ingest into its knowledge base.

```
Corpus Manifest (YAML)
       ↓
Validated Source Entries
       ↓
Existing Phase 1B Ingestion Pipeline (Fetch, Extract, Normalize, Fingerprint)
       ↓
Existing Phase 1C-A Knowledge Persistence (PostgreSQL / In-Memory)
```

> **CORE ARCHITECTURAL PRINCIPLE**  
> SANGYAN must **never** silently crawl the open web, search engines, or discover PDFs autonomously. The knowledge corpus is an explicit, human-curated specification with audited provenance and cryptographic deduplication.

---

## Manifest Structure

Corpus manifests are written in standard YAML and strictly validated via Pydantic:

```yaml
corpus_version: "2026-10-04-v1"

sources:
  - source_id: "sebi_cir_grievance_2023"
    source_class: "REGULATORY"
    authority: "SEBI"
    url: "https://www.sebi.gov.in/legal/circulars/example.pdf"
    expected_domain: "sebi.gov.in"
    document_type: "Circular"
    topic:
      - investor_grievance
    description: "SEBI circular on online dispute resolution."

  - source_id: "broker_dp_tariff_2024"
    source_class: "ORGANISATION_POLICY"
    organisation_id: "ORG_ZERODHA"
    url: "https://zerodha.com/charges.html"
    expected_domain: "zerodha.com"
    document_type: "Fee Schedule"
    topic:
      - charges
      - demat
```

### Top-Level Fields

- `corpus_version` *(required, non-empty string)*: Explicit version identifier (e.g. `2026-10-04-v1`). Controlled by the researcher/maintainer.
- `sources` *(required, non-empty list)*: Explicit array of source definitions.

### Source Entry Fields

| Field | Type | Mandatory? | Description |
|---|---|---|---|
| `source_id` | `string` | **Yes** | Unique, stable identifier (e.g. `sebi_investor_grievance`). Random IDs prohibited. |
| `source_class` | `SourceClass` | **Yes** | `REGULATORY`, `ORGANISATION_POLICY`, `ORGANISATION_PROCEDURE`, `ORGANISATION_FAQ`, or `SECONDARY_SOURCE`. |
| `url` | `HttpUrl` | **Yes** | HTTP or HTTPS URL. Embedded credentials and local paths are rejected. |
| `organisation_id`| `string` | **Conditional** | **Mandatory** for `ORGANISATION_POLICY`, `ORGANISATION_PROCEDURE`, `ORGANISATION_FAQ`. |
| `authority` | `string` | Optional | Regulatory authority (e.g. `SEBI`, `RBI`, `NSE`). |
| `document_type` | `string` | Optional | Classification (e.g. `Circular`, `Master Circular`, `Policy`, `FAQ`). |
| `topic` | `list[str]` | Optional | Domain topics (e.g. `[investor_grievance, dispute_resolution]`). |
| `expected_domain`| `string` | Optional | Authoritative domain for redirect validation and SSRF protection. |
| `description` | `string` | Optional | Human-readable documentation of document scope. |

---

## Validation Rules

1. **Security & Sandboxing**: Manifests are configuration files parsed via `yaml.safe_load`. YAML is never executed as Python code.
2. **Epistemic Invariant**: Any source classed as `ORGANISATION_POLICY`, `ORGANISATION_PROCEDURE`, or `ORGANISATION_FAQ` **must** specify an `organisation_id`.
3. **URL Sandboxing**: Only `http` and `https` schemes are accepted. Local file paths (`file://`, `/etc`, `C:\`) and embedded credentials (`http://user:pass@host`) fail validation immediately.
4. **Stable Identifiers**: `source_id` values must be non-empty and unique within the manifest.
5. **No Embedded Content**: Source models contain **only** acquisition metadata; raw text or document bodies are never embedded into manifest files.

---

## CLI Usage

### 1. Dry Run (Manifest Validation & Planning)
Performs zero HTTP requests and zero database writes:

```powershell
python -m ai.app.corpus.runner --manifest ai/corpus/manifest.example.yaml --dry-run
```

### 2. Live Corpus Ingestion (In-Memory Repository)
Executes deterministic fetching and normalization, persisting in memory:

```powershell
python -m ai.app.corpus.runner --manifest ai/corpus/manifest.example.yaml
```

### 3. Live Corpus Ingestion (PostgreSQL Repository)
Persists ingested documents, sections, and audit logs into PostgreSQL:

```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres:<password>@localhost:5432/ai_knowledge"
python -m ai.app.corpus.runner --manifest ai/corpus/manifest.example.yaml --use-db
```

---

## Idempotency & Failure Handling

- **Deduplication**: Reuses Phase 1B SHA-256 fingerprinting. Re-running the exact same manifest twice detects identical content hashes and marks subsequent runs as `DUPLICATE` without duplicating database rows.
- **Fault Tolerance**: If an individual source fails (e.g. HTTP 404, unsupported MIME type, network timeout), the failure is isolated and recorded in the structured report with the exact stage (`FETCH`, `EXTRACTION`, etc.) and error message without aborting remaining sources.
