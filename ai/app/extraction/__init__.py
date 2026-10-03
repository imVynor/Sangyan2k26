"""SANGYAN Evidentiary Fact Extraction Layer.

Public exports:
- FactExtractor
- FactNormalizer
- DocumentExtractor
- CaseIntegrator
- FactExtractionRequest
- FactExtractionResult
- ExtractedFact
- FactType
- FactEpistemicStatus
- ExtractionSupportLevel
- SourceSpan
- OCRProvider
- FallbackOCRProvider
"""

from ai.app.extraction.case_integrator import CaseIntegrator
from ai.app.extraction.contracts import (
    ExtractedFact,
    ExtractionSupportLevel,
    FactEpistemicStatus,
    FactExtractionRequest,
    FactExtractionResult,
    FactType,
    SourceSpan,
)
from ai.app.extraction.document_extractor import (
    DocumentExtractionPayload,
    DocumentExtractor,
    DocumentSpan,
    FallbackOCRProvider,
    OCRProvider,
)
from ai.app.extraction.extractor import FactExtractor
from ai.app.extraction.fact_normalizer import FactNormalizer

from ai.app.extraction.provision_extractor import (
    DeterministicProvisionExtractor,
    LLMProvisionExtractor,
    ProvisionExtractor,
)

__all__ = [
    "FactExtractor",
    "FactNormalizer",
    "DocumentExtractor",
    "DocumentSpan",
    "DocumentExtractionPayload",
    "CaseIntegrator",
    "FactExtractionRequest",
    "FactExtractionResult",
    "ExtractedFact",
    "FactType",
    "FactEpistemicStatus",
    "ExtractionSupportLevel",
    "SourceSpan",
    "OCRProvider",
    "FallbackOCRProvider",
    "ProvisionExtractor",
    "DeterministicProvisionExtractor",
    "LLMProvisionExtractor",
]
