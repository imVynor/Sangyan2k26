"""Unit tests for JSON utilities, extraction, and Pydantic validation."""

import pytest
from pydantic import BaseModel, Field

from ai.app.utils.json_utils import (
    JSONParsingError,
    SchemaValidationError,
    extract_json_text,
    parse_and_validate,
    parse_strict_json,
)


class DummySampleSchema(BaseModel):
    name: str
    count: int
    is_active: bool = True
    tags: list[str] = Field(default_factory=list)


def test_extract_json_text_plain():
    text = '{"name": "test", "count": 1}'
    assert extract_json_text(text) == '{"name": "test", "count": 1}'


def test_extract_json_text_markdown_fence():
    text = '```json\n{"name": "test", "count": 1}\n```'
    assert extract_json_text(text) == '{"name": "test", "count": 1}'

    raw_fence = '```\n{"name": "test", "count": 1}\n```'
    assert extract_json_text(raw_fence) == '{"name": "test", "count": 1}'


def test_parse_strict_json_valid():
    text = '{"name": "Zerodha", "count": 42}'
    data = parse_strict_json(text)
    assert data == {"name": "Zerodha", "count": 42}


def test_parse_strict_json_malformed():
    """Ensure malformed JSON fails explicitly without silent regex repair."""
    malformed = '{"name": "broken", "count": 42,}'  # trailing comma
    with pytest.raises(JSONParsingError) as exc_info:
        parse_strict_json(malformed)
    assert "Failed to parse JSON" in str(exc_info.value)
    assert exc_info.value.raw_text == malformed


def test_parse_and_validate_success():
    payload = '{"name": "test_entity", "count": 5, "tags": ["tag1", "tag2"]}'
    model = parse_and_validate(payload, DummySampleSchema)
    assert model.name == "test_entity"
    assert model.count == 5
    assert model.is_active is True
    assert model.tags == ["tag1", "tag2"]


def test_parse_and_validate_schema_mismatch():
    """Fails when required field is missing."""
    payload = '{"name": "test_entity"}'  # missing required 'count'
    with pytest.raises(SchemaValidationError) as exc_info:
        parse_and_validate(payload, DummySampleSchema)
    assert "Schema validation failed" in str(exc_info.value)
    assert exc_info.value.errors[0]["loc"] == ("count",)


def test_parse_and_validate_wrong_type():
    """Fails when field has incompatible type."""
    payload = '{"name": "test_entity", "count": "not_an_int"}'
    with pytest.raises(SchemaValidationError):
        parse_and_validate(payload, DummySampleSchema)


def test_parse_and_validate_rejects_non_dict():
    """Fails when root is not a dictionary."""
    payload = '["item1", "item2"]'
    with pytest.raises(SchemaValidationError) as exc_info:
        parse_and_validate(payload, DummySampleSchema)
    assert "Expected a JSON object (dict)" in str(exc_info.value)
