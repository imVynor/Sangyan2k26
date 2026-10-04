"""Tests for core schemas and epistemic data models."""

import pytest
from pydantic import ValidationError

from ai.app.models.schemas import (
    CaseUnderstanding,
    Claim,
    Entity,
    EpistemicStatus,
    Fact,
    Hypothesis,
    LLMRequest,
    LLMResponse,
    Message,
    Role,
    Unknown,
)


def test_message_valid():
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"

    sys_msg = Message(role=Role.SYSTEM.value, content="Be concise")
    assert sys_msg.role == "system"


def test_message_invalid_role():
    with pytest.raises(ValidationError):
        Message(role="invalid_role", content="Hello")


def test_llm_request():
    req = LLMRequest(
        messages=[Message(role="user", content="Test")],
        temperature=0.7,
        max_tokens=100,
        response_schema_name="CaseUnderstanding",
    )
    assert len(req.messages) == 1
    assert req.temperature == 0.7
    assert req.max_tokens == 100
    assert req.response_schema_name == "CaseUnderstanding"


def test_llm_response_optional_tokens():
    # Token counts must be optional per requirement
    resp = LLMResponse(
        content="Response text",
        model="qwen3.8:27b",
        provider="ollama",
        latency_ms=123.45,
    )
    assert resp.prompt_tokens is None
    assert resp.completion_tokens is None
    assert resp.total_tokens is None
    assert resp.raw_response is None
    assert resp.latency_ms == 123.45


def test_epistemic_case_understanding():
    """Verify epistemic separation in CaseUnderstanding."""
    case = CaseUnderstanding(
        intent="report_unauthorized_debit",
        entities=[
            Entity(name="Zerodha", category="broker", details="Discount broker")
        ],
        facts=[
            Fact(
                statement="₹500 debited on 2026-10-01",
                status=EpistemicStatus.USER_ASSERTED,
                source="user_narrative",
            )
        ],
        claims=[
            Claim(
                statement="This debit is illegal and violates SEBI rules",
                status=EpistemicStatus.USER_ASSERTED,
                basis="User believes fees are prohibited",
            )
        ],
        unknowns=[
            Unknown(
                item="Ledger narration of ₹500 debit",
                importance="critical",
                reason="Needed to identify charge type (AMC vs DP vs penalty)",
            )
        ],
        hypotheses=[
            Hypothesis(
                description="Quarterly account maintenance charge",
                likelihood="plausible",
                investigation_needed="Check tariff schedule",
            )
        ],
        next_question="What is the exact narration next to the ₹500 entry in your statement?",
    )

    data = case.model_dump()
    assert data["intent"] == "report_unauthorized_debit"
    assert len(data["entities"]) == 1
    assert data["facts"][0]["status"] == "USER_ASSERTED"
    assert data["claims"][0]["status"] == "USER_ASSERTED"
    assert data["unknowns"][0]["importance"] == "critical"
    assert data["hypotheses"][0]["description"] == "Quarterly account maintenance charge"

    # Verify round-trip deserialization
    deserialized = CaseUnderstanding.model_validate(data)
    assert deserialized.facts[0].statement == "₹500 debited on 2026-10-01"
    assert deserialized.claims[0].statement == "This debit is illegal and violates SEBI rules"


def test_schema_requires_valid_epistemic_status():
    with pytest.raises(ValidationError):
        Fact(statement="Invalid status test", status="NOT_A_VALID_STATUS")
