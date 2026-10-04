"""SANGYAN Auditable Generation Layer.

Public exports:
- AuditableResponseGenerator
- GenerationValidator
- GenerationValidationResult
- CitationRenderer
- CitationReference
- GeneratedFinding
- GeneratedResponse
"""

from ai.app.generation.citation_renderer import CitationRenderer
from ai.app.generation.contracts import (
    CitationReference,
    GeneratedFinding,
    GeneratedResponse,
)
from ai.app.generation.generator import AuditableResponseGenerator
from ai.app.generation.validator import GenerationValidationResult, GenerationValidator

__all__ = [
    "AuditableResponseGenerator",
    "GenerationValidator",
    "GenerationValidationResult",
    "CitationRenderer",
    "CitationReference",
    "GeneratedFinding",
    "GeneratedResponse",
]
