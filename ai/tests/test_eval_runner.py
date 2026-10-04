"""Tests for the evaluation runner and case loader."""

import json
import httpx
import pytest

from ai.app.models.ollama import OllamaProvider
from ai.evals.runners.eval_schema import EvaluationCase
from ai.evals.runners.runner import evaluate_single_case, load_benchmark_cases


def test_load_benchmark_cases():
    cases = load_benchmark_cases()
    assert len(cases) == 10
    case_ids = [c.id for c in cases]
    assert "case_01_fact_extraction" in case_ids
    assert "case_02_claim_vs_fact" in case_ids
    assert "case_05_hindi_input" in case_ids
    assert "case_06_hinglish_input" in case_ids
    assert "case_08_hallucination_resistance" in case_ids


@pytest.mark.asyncio
async def test_evaluate_single_case_success_mock():
    case = EvaluationCase(
        id="test_case_mock",
        category="mock_category",
        system_prompt="Extract case details",
        user_prompt="I was charged ₹100",
        expected_behavior="Extract 100",
        expected_schema="CaseUnderstanding",
    )

    valid_payload = {
        "intent": "report_charge",
        "entities": [],
        "facts": [{"statement": "Charged ₹100", "status": "USER_ASSERTED"}],
        "claims": [],
        "unknowns": [],
        "hypotheses": [],
        "next_question": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gemma4:12b",
                "message": {"role": "assistant", "content": json.dumps(valid_payload)},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434")
    provider = OllamaProvider(model_name="gemma4:12b", client=client)

    result = await evaluate_single_case(provider, case)
    assert result.success is True
    assert result.parsed_output is not None
    assert result.parsed_output["intent"] == "report_charge"
    assert result.validation_error is None
    assert "Successfully validated" in result.notes


@pytest.mark.asyncio
async def test_evaluate_single_case_validation_failure_mock():
    case = EvaluationCase(
        id="test_case_fail_mock",
        category="mock_category",
        system_prompt="Extract case details",
        user_prompt="I was charged ₹100",
        expected_behavior="Extract 100",
        expected_schema="CaseUnderstanding",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gemma4:12b",
                "message": {"role": "assistant", "content": "not json content"},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434")
    provider = OllamaProvider(model_name="gemma4:12b", client=client)

    result = await evaluate_single_case(provider, case)
    assert result.success is False
    assert result.parsed_output is None
    assert result.validation_error is not None
