# SANGYAN API Transport Layer (Phase 6B)

The **SANGYAN API Transport Layer** exposes the authoritative internal reasoning engine (`CaseOrchestrator`) via high-performance FastAPI REST endpoints and real-time WebSocket event streaming.

```text
       HTTP / REST Client                 WebSocket Subscriber
               │                                   │
               ▼                                   ▼
        FastAPI Routers                     WebSocket Handler
   (/api/v1/cases, /turns, /audit)       (/api/v1/ws/cases/{id})
               │                                   │
               ▼                                   ▼
       Transport Schemas                    ConnectionManager
     (CaseView, TurnView)                  (Event Envelope / Replay)
               │                                   │
               └─────────────────┬─────────────────┘
                                 ▼
                         CASE ORCHESTRATOR
                (Authoritative Execution Boundary)
                                 │
         ┌──────────────┬────────┴───────┬──────────────┐
         ▼              ▼                ▼              ▼
     Extraction     Evidence         Retrieval      Assessment
                     Policy                        (RuleEvaluator)
```

---

## Core Transport Principle

> **Transport must remain thin. The `CaseOrchestrator` remains the single authoritative execution boundary.**

Under no circumstances do route handlers or WebSocket handlers directly invoke `RuleEvaluator`, hybrid retrieval, `EvidencePolicyResolver`, or direct database mutations. All mutations flow strictly through:

```python
CaseOrchestrator.process_turn(...)
```

---

## 1. REST API Specification

Base Path: `/api/v1`

### 1.1 Create Case
* **Endpoint**: `POST /api/v1/cases`
* **Status**: `201 Created`
* **Headers**: `Idempotency-Key` (Optional)
* **Request**:
  ```json
  {
    "initial_message": "Zerodha charged me ₹50 for selling equity delivery shares.",
    "language": "en",
    "metadata": {}
  }
  ```
* **Response**:
  ```json
  {
    "case_id": "CASE-9F2B81C0",
    "version": 1,
    "status": "REQUIRES_CLARIFICATION",
    "turn_id": "TRN-4A9211D8",
    "response": {
      "case_id": "CASE-9F2B81C0",
      "turn_id": "TRN-4A9211D8",
      "previous_version": 0,
      "new_version": 1,
      "previous_status": "DRAFT",
      "new_status": "REQUIRES_CLARIFICATION",
      "status_transition": "DRAFT -> REQUIRES_CLARIFICATION",
      "new_facts": {
        "charged_amount": "50.00",
        "organisation": "ORG_ZERODHA"
      },
      "claims": [
        {
          "claim_id": "CLM-109282",
          "field": "charged_amount",
          "claimed_value": "50.00",
          "source_class": "USER_ASSERTED",
          "status": "SUPPORTED"
        }
      ],
      "assessment": {
        "assessment_id": "ASM-CASE-9F2B81C0",
        "status": "EVIDENCE_INSUFFICIENT",
        "summary": "Status: EVIDENCE_INSUFFICIENT",
        "overall_support_level": "HIGH_SUPPORT",
        "findings": []
      },
      "assessment_delta": {
        "previous_status": null,
        "new_status": "EVIDENCE_INSUFFICIENT",
        "status_changed": true,
        "facts_changed": ["charged_amount", "organisation"],
        "cause": {
          "primary_fact": "charged_amount",
          "description": "Assessment transitioned from None to EVIDENCE_INSUFFICIENT driven by charged_amount modification."
        }
      },
      "clarification_questions": [
        {
          "question_id": "Q-829102",
          "field_name": "transaction_type",
          "text": "Was this trade executed as Equity Delivery (CNC) or Intraday (MIS)?",
          "priority": "HIGH",
          "rationale": "Zerodha charges ₹0 for Delivery trades and ₹20 for Intraday trades.",
          "suggested_evidence_types": ["USER_STATEMENT", "DOCUMENT"]
        }
      ],
      "explanation": "To determine whether Zerodha's fee exceeds regulatory and tariff limits, we need to know the transaction type.",
      "generation_status": "COMPLETED"
    }
  }
  ```

### 1.2 Submit Dialogue Turn
* **Endpoint**: `POST /api/v1/cases/{case_id}/turns`
* **Status**: `200 OK`
* **Headers**: `Idempotency-Key` (Optional)
* **Request**:
  ```json
  {
    "message": "It was an equity delivery trade.",
    "declined_field": null,
    "expected_version": 1
  }
  ```

### 1.3 Upload Evidence Document
* **Endpoint**: `POST /api/v1/cases/{case_id}/evidence`
* **Status**: `200 OK`
* **Form Parameters**:
  - `file`: Binary file (`application/pdf`, `image/png`, `image/jpeg`, `text/plain`, `text/csv`)
  - `description`: String explanation (optional)
  - `expected_version`: Integer for concurrency check (optional)

### 1.4 Get Case Projection
* **Endpoint**: `GET /api/v1/cases/{case_id}`
* **Status**: `200 OK`
* **Response**: Authoritative `CaseView` containing active facts, preserved claims, contradictions, evidence items, and current assessment snapshot.

### 1.5 Query Audit Trail
* **Endpoint**: `GET /api/v1/cases/{case_id}/audit?after_version=1&limit=50`
* **Status**: `200 OK`
* **Response**: Immutable event stream with version tracking, timestamps, actors, and assessment correlation.

---

## 2. WebSocket Real-Time Event Streaming

* **URL**: `/api/v1/ws/cases/{case_id}`
* **Query Parameters**: `last_seen_version` (Optional integer)

### 2.1 Envelope Format
```json
{
  "event_id": "WSE-8A91BC21",
  "case_id": "CASE-9F2B81C0",
  "turn_id": "TRN-4A9211D8",
  "version": 2,
  "event_type": "ASSESSMENT_UPDATED",
  "timestamp": "2026-10-04T11:05:00.000Z",
  "payload": {
    "previous_status": "EVIDENCE_INSUFFICIENT",
    "new_status": "VIOLATION_CONFIRMED"
  }
}
```

### 2.2 Event Types
- `CASE_CREATED`, `CASE_REOPENED`
- `FACT_EXTRACTED`
- `CLAIM_REGISTERED`, `CLAIM_RESOLVED`
- `EVIDENCE_ACCEPTED`, `EVIDENCE_REJECTED`
- `RETRIEVAL_EXECUTED`
- `ASSESSMENT_EXECUTED`, `ASSESSMENT_UPDATED`
- `CLARIFICATION_REQUESTED`
- `ACTION_INTENT_CREATED`
- `GENERATION_COMPLETED`
- `TURN_COMPLETED`

### 2.3 Reconnect & Replay Protocol
When a client drops connectivity and reconnects:
1. Connects with `?last_seen_version=N` or sends JSON message: `{"type": "replay", "last_seen_version": N}`.
2. The server queries the authoritative `CaseState.interaction_history` and replays all missed events where `case_version > N`.
3. Client seamlessly resumes listening for live broadcast events.

---

## 3. Concurrency & Idempotency

### Optimistic Concurrency
Clients pass `expected_version` in turn requests:
- If `expected_version == current_version`: Turn proceeds.
- If `expected_version != current_version`: Returns **HTTP 409 Conflict**:
  ```json
  {
    "error": {
      "code": "CASE_VERSION_CONFLICT",
      "message": "CASE_VERSION_CONFLICT: Expected version 1, but found 2.",
      "current_version": 2,
      "is_retryable": true
    },
    "request_id": "REQ-716298"
  }
  ```
  **Zero mutations or partial events are committed.**

### Idempotency
Clients include `Idempotency-Key` header:
- Repeated requests return the identical, cached logical turn result.
- Avoids duplicated reasoning turns or redundant model inference.

---

## 4. Failure Isolation & Downstream Presentation

Operational failures are mapped cleanly without state corruption:
- `ExtractionError` $\rightarrow$ `502 EXTRACTION_FAILED`
- `RetrievalError` $\rightarrow$ `503 RETRIEVAL_FAILED`
- `AssessmentError` $\rightarrow$ `500 ASSESSMENT_FAILED`
- `GenerationError`: **Does NOT fail the turn.** The epistemic assessment remains authoritative and the turn succeeds (`200 OK`) with `generation_status: "FAILED"`.

---

## 5. Security & Authentication Boundary

* `CurrentPrincipal`: Pluggable authentication context resolving user identity, role (`investor`, `analyst`, `admin`), and scoped case authorization.
* `CaseAccessPolicy`: Evaluates authorization per case before executing orchestrator turns.
* Security isolation: Never leaks internal stack traces, database credentials, or internal filesystem paths.

---

## 6. Local Development & Running the Server

Start the development server with live reload:

```bash
uvicorn ai.app.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Open interactive Swagger UI:
```text
http://localhost:8000/api/v1/docs
```
