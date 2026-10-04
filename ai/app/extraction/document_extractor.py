"""Deterministic Document Content Extraction and Provenance Preservation for SANGYAN.

Epistemic foundation:
- Accepts PDF, HTML, plain text, and OCR inputs.
- Reuses Phase 1 deterministic parsing stack.
- Preserves page numbers, section headers, and character coordinates.
- Abstract OCRProvider decouples OCR engines without mandatory dependencies.
- Explicitly flags OCR_UNAVAILABLE when OCR engine is absent.
"""

from io import BytesIO
import logging
from typing import Any, Protocol
from pydantic import BaseModel, Field

from ai.app.extraction.contracts import SourceSpan
from ai.app.ingestion.html_extractor import extract_html
from ai.app.ingestion.pdf_extractor import extract_pdf

logger = logging.getLogger("sangyan.extraction.document_extractor")


class OCRProvider(Protocol):
    """Protocol boundary for OCR providers (Tesseract, PaddleOCR, Cloud OCR)."""

    def is_available(self) -> bool:
        """Check if OCR runtime dependencies are installed and available."""
        ...

    def extract_text(self, image_bytes: bytes) -> str:
        """Extract text from raw image bytes."""
        ...


class FallbackOCRProvider:
    """Default fallback OCR provider when no external OCR runtime is configured."""

    def is_available(self) -> bool:
        return False

    def extract_text(self, image_bytes: bytes) -> str:
        raise RuntimeError("OCR_UNAVAILABLE: No OCR provider is configured in this environment.")


class DocumentSpan(BaseModel):
    """Extracted text section with page and offset coordinates."""
    text: str
    page_number: int | None = None
    section_title: str | None = None
    start_char: int = 0
    end_char: int = 0


class DocumentExtractionPayload(BaseModel):
    """Extracted document content with structural metadata."""
    document_id: str
    raw_content: str
    content_format: str = "text"  # 'pdf', 'html', 'text', 'ocr'
    spans: list[DocumentSpan] = Field(default_factory=list)
    page_count: int = 1
    ocr_used: bool = False


class DocumentExtractor:
    """Extracts text and structural location metadata from uploaded documents."""

    def __init__(self, ocr_provider: OCRProvider | None = None) -> None:
        self.ocr_provider = ocr_provider or FallbackOCRProvider()

    def extract_from_pdf_bytes(
        self,
        raw_bytes: bytes,
        document_id: str,
    ) -> DocumentExtractionPayload:
        """Deterministically extract pages and offsets from PDF bytes."""
        extracted = extract_pdf(raw_bytes)
        spans: list[DocumentSpan] = []
        cumulative_len = 0

        for sec in extracted.sections:
            page_num = int(sec.section_id.replace("page_", "")) if "page_" in sec.section_id else 1
            sec_len = len(sec.content)
            spans.append(
                DocumentSpan(
                    text=sec.content,
                    page_number=page_num,
                    section_title=sec.heading,
                    start_char=cumulative_len,
                    end_char=cumulative_len + sec_len,
                )
            )
            cumulative_len += sec_len + 2  # account for newline

        return DocumentExtractionPayload(
            document_id=document_id,
            raw_content=extracted.full_text,
            content_format="pdf",
            spans=spans,
            page_count=len(extracted.sections),
            ocr_used=False,
        )

    def extract_from_html(
        self,
        html_text: str,
        document_id: str,
    ) -> DocumentExtractionPayload:
        """Extract clean text and sections from HTML."""
        extracted = extract_html(html_text)
        spans: list[DocumentSpan] = []
        cumulative_len = 0

        for sec in extracted.sections:
            sec_len = len(sec.content)
            spans.append(
                DocumentSpan(
                    text=sec.content,
                    page_number=1,
                    section_title=sec.heading,
                    start_char=cumulative_len,
                    end_char=cumulative_len + sec_len,
                )
            )
            cumulative_len += sec_len + 2

        return DocumentExtractionPayload(
            document_id=document_id,
            raw_content=extracted.full_text,
            content_format="html",
            spans=spans,
            page_count=1,
            ocr_used=False,
        )

    def extract_from_text(
        self,
        text: str,
        document_id: str,
    ) -> DocumentExtractionPayload:
        """Wrap plain text with character coordinates."""
        cleaned = text.strip()
        span = DocumentSpan(
            text=cleaned,
            page_number=1,
            section_title="Body",
            start_char=0,
            end_char=len(cleaned),
        )
        return DocumentExtractionPayload(
            document_id=document_id,
            raw_content=cleaned,
            content_format="text",
            spans=[span],
            page_count=1,
            ocr_used=False,
        )

    def extract_from_image(
        self,
        image_bytes: bytes,
        document_id: str,
    ) -> DocumentExtractionPayload:
        """Extract text from screenshot or scanned receipt via OCRProvider."""
        if not self.ocr_provider.is_available():
            raise RuntimeError("OCR_UNAVAILABLE")

        text = self.ocr_provider.extract_text(image_bytes)
        return self.extract_from_text(text, document_id)
