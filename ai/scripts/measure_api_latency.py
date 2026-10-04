"""Measure HTTP transport overhead vs orchestrator turn latency.

Epistemic foundation:
- Explicitly distinguishes in-memory orchestration latency from model-backed latency.
- Isolates HTTP serialization, middleware routing, and transport parsing overheads.
"""

import time
from starlette.testclient import TestClient
from ai.app.api import create_app
from ai.app.case.contracts import CaseEventType
from ai.app.orchestration.contracts import OrchestrationInputEvent
from ai.app.orchestration.orchestrator import CaseOrchestrator


def benchmark_latencies(n_iterations: int = 50) -> dict[str, float]:
    orchestrator = CaseOrchestrator()
    app = create_app(orchestrator=orchestrator)
    client = TestClient(app)

    # 1. Measure direct orchestrator overhead
    orchestrator_durations = []
    for i in range(n_iterations):
        case_id = f"BENCH-ORCH-{i}"
        inp = OrchestrationInputEvent(
            event_type=CaseEventType.USER_MESSAGE_RECEIVED,
            complaint_text="Zerodha charged 50 rupees for delivery trade",
            user_message="Zerodha charged 50 rupees for delivery trade",
        )
        t0 = time.perf_counter()
        _ = None
        import asyncio
        res = asyncio.run(orchestrator.process_turn(case_id, inp))
        t1 = time.perf_counter()
        orchestrator_durations.append((t1 - t0) * 1000)

    avg_orchestrator_ms = sum(orchestrator_durations) / len(orchestrator_durations)

    # 2. Measure HTTP endpoint overhead (including transport, serialization, middleware)
    http_durations = []
    for i in range(n_iterations):
        payload = {
            "initial_message": "Zerodha charged 50 rupees for delivery trade",
            "language": "en",
        }
        t0 = time.perf_counter()
        resp = client.post("/api/v1/cases", json=payload)
        t1 = time.perf_counter()
        assert resp.status_code == 201
        http_durations.append((t1 - t0) * 1000)

    avg_http_ms = sum(http_durations) / len(http_durations)
    transport_overhead_ms = max(0.0, avg_http_ms - avg_orchestrator_ms)

    results = {
        "avg_orchestrator_ms": avg_orchestrator_ms,
        "avg_http_ms": avg_http_ms,
        "transport_overhead_ms": transport_overhead_ms,
    }

    print("==================================================")
    print("SANGYAN Phase 6B Latency Profiling (In-Memory)")
    print("==================================================")
    print(f"Direct Orchestrator Turn: {avg_orchestrator_ms:.2f} ms")
    print(f"Total HTTP Round-Trip:    {avg_http_ms:.2f} ms")
    print(f"HTTP Transport Overhead:  {transport_overhead_ms:.2f} ms")
    print("==================================================")
    return results


if __name__ == "__main__":
    benchmark_latencies(20)
