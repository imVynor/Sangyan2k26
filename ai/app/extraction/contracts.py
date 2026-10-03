"""Evidentiary Fact Extraction Contracts and Schemas for SANGYAN.

Epistemic foundation:
- Extracts structured facts from unstructured natural language and documents.
- Preserves exact source spans, character offsets, and document coordinates.
- Explicit epistemic statuses: OBSERVED, MODEL_INTERPRETATION, DERIVED, USER_ASSERTED, DOCUMENT_ASSERTED.
- Produces CANDIDATE_FACT and evidence proposals, NEVER directly mutating authoritative case state.
- Strictly prohibits extracting legal conclusions (e.g. 'violation = true').
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import (
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceType,
)


class FactType(str, Enum):
    """Data type of the extracted empirical fact."""
    STRING = "STRING"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    CURRENCY = "CURRENCY"
    DATE = "DATE"
    DATETIME = "DATETIME"
    BOOLEAN = "BOOLEAN"
    ENUM = "ENUM"
    ENTITY = "ENTITY"
    DURATION = "DURATION"
    PERCENTAGE = "PERCENTAGE"


class FactEpistemicStatus(str, Enum):
    """Categorical classification of the epistemic origin of an extracted fact."""
    OBSERVED = "OBSERVED"
    MODEL_INTERPRETATION = "MODEL_INTERPRETATION"
    DERIVED = "DERIVED"
    USER_ASSERTED = "USER_ASSERTED"
    DOCUMENT_ASSERTED = "DOCUMENT_ASSERTED"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"


class ExtractionSupportLevel(str, Enum):
    """Qualitative grounding support level for an extracted fact."""
    DIRECT = "DIRECT"
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    WEAK = "WEAK"
    UNSUPPORTED = "UNSUPPORTED"


class SourceSpan(BaseModel):
    """Verbatim location and textual anchor in source material."""
    text: str = Field(description="Exact snippet verbatim from input text.")
    start_char: int | None = Field(default=None, description="Starting character index.")
    end_char: int | None = Field(default=None, description="Ending character index.")
    page_number: int | None = Field(default=None, description="PDF or document page number.")
    section: str | None = Field(default=None, description="Section or table header.")
    document_id: str | None = Field(default=None, description="Identifier of source document.")


class ExtractedFact(BaseModel):
    """Atomic extracted empirical fact with provenance and epistemic classification."""
    field: str = Field(description="Canonical field name (e.g. 'charged_amount', 'transaction_date', 'organisation').")
    raw_value: Any = Field(description="Raw string value from text.")
    normalized_value: Any = Field(description="Normalized typed value (Decimal for money, date for dates).")
    fact_type: FactType = Field(default=FactType.STRING)
    source_span: SourceSpan = Field(description="Exact source span anchoring this fact.")
    epistemic_status: FactEpistemicStatus = Field(default=FactEpistemicStatus.USER_ASSERTED)
    confidence: ExtractionSupportLevel = Field(default=ExtractionSupportLevel.DIRECT)
    extraction_method: str = Field(default="RULE_OR_LLM", description="Extraction channel used.")
    notes: str | None = None


class FactExtractionRequest(BaseModel):
    """Input payload for evidentiary fact extraction."""
    input_text: str = Field(description="Raw user text, complaint narrative, or document content.")
    source_id: str = Field(description="Source identifier (e.g. 'user_msg_001', 'contract_note.pdf').")
    source_type: EvidenceType = Field(default=EvidenceType.USER_STATEMENT)
    reference_date: date | None = Field(
        default=None,
        description="Explicit reference date for resolving relative dates like 'yesterday' or 'last week'.",
    )
    language: str = Field(default="en", description="Source language ('en', 'hi', 'hinglish').")
    document_metadata: dict[str, Any] = Field(default_factory=dict)


class FactExtractionResult(BaseModel):
    """Output envelope of the evidentiary fact extraction service."""
    extraction_id: str
    source_id: str
    extracted_facts: list[ExtractedFact] = Field(default_factory=list)
    evidence_proposals: list[EvidenceItem] = Field(default_factory=list)
    case_fact_candidates: dict[str, Any] = Field(default_factory=dict)
    contradictions: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    extraction_warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
