"""JSON utility functions for safe parsing and Pydantic validation.

Follows strict epistemic constraints:
- No silent acceptance of malformed JSON.
- No heuristic regex-based JSON 'repair' in v1.
- Explicit errors when parsing or schema validation fails.
"""

import json
from typing import Any, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class JSONParsingError(Exception):
    """Raised when model output is not valid JSON."""

    def __init__(self, message: str, raw_text: str):
        super().__init__(message)
        self.raw_text = raw_text


class SchemaValidationError(Exception):
    """Raised when JSON output fails Pydantic schema validation."""

    def __init__(self, message: str, errors: list[dict[str, Any]], parsed_data: Any):
        super().__init__(message)
        self.errors = errors
        self.parsed_data = parsed_data


def extract_json_text(text: str) -> str:
    """Extract JSON string, stripping markdown code block fences if present.
    
    Does NOT attempt fuzzy regex heuristics or repair broken syntax.
    """
    cleaned = text.strip()
    
    # Handle standard markdown fenced JSON blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
            
    return cleaned


def parse_strict_json(text: str) -> Any:
    """Strictly parse raw string to JSON object/array.
    
    Raises JSONParsingError if invalid.
    """
    candidate = extract_json_text(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JSONParsingError(
            f"Failed to parse JSON: {exc.msg} at line {exc.lineno}, col {exc.colno}",
            raw_text=text,
        ) from exc


def parse_and_validate(text: str, schema: type[T]) -> T:
    """Parse JSON and validate against a target Pydantic schema.
    
    Raises:
        JSONParsingError: if JSON decode fails.
        SchemaValidationError: if Pydantic model validation fails.
    """
    data = parse_strict_json(text)
    if not isinstance(data, dict):
        raise SchemaValidationError(
            f"Expected a JSON object (dict) matching {schema.__name__}, got {type(data).__name__}",
            errors=[{"loc": (), "msg": "Expected dictionary", "type": "type_error.dict"}],
            parsed_data=data,
        )

    try:
        return schema.model_validate(data)
    except ValidationError as val_err:
        raise SchemaValidationError(
            f"Schema validation failed for {schema.__name__}: {val_err.error_count()} error(s)",
            errors=val_err.errors(),
            parsed_data=data,
        ) from val_err
