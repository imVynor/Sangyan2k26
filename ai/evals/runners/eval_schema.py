"""Evaluation schemas for SANGYAN model benchmarking."""

from typing import Any
from pydantic import BaseModel, Field


class EvaluationCase(BaseModel):
    """Specification for a single evaluation test case."""
    id: str = Field(description="Unique case identifier, e.g. 'case_01_fact_extraction'")
    category: str = Field(description="Evaluation category, e.g. 'epistemic_distinction', 'multilingual'")
    system_prompt: str = Field(description="System instructions provided to the model")
    user_prompt: str = Field(description="Simulated investor grievance prompt")
    expected_behavior: str = Field(description="Description of expected reasoning, distinctions, and behavior")
    expected_schema: str | None = Field(
        default=None,
        description="Name of Pydantic schema to validate output against, if structured output is tested"
    )


class EvaluationResult(BaseModel):
    """Result of running an evaluation case on a specific model."""
    case_id: str
    model: str
    success: bool
    latency_ms: float
    output: str
    parsed_output: dict[str, Any] | None = None
    validation_error: str | None = None
    notes: str | None = None


class EvaluationReport(BaseModel):
    """Aggregate report across multiple models and test cases."""
    timestamp: str
    models_evaluated: list[str]
    total_cases: int
    summary_by_model: dict[str, dict[str, Any]]
    results: list[EvaluationResult]
