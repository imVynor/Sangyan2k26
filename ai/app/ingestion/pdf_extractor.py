"""Deterministic PDF text extraction preserving page boundaries and ordering.

Uses pypdf for deterministic byte-level parsing.
Preserves page structure:
Page 1
 └── page text
Page 2
 └── page text
If the PDF is empty or purely scanned images without a text layer, fails explicitly.
"""

import io
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ai.app.ingestion.errors import ExtractionError
from ai.app.ingestion.models import ExtractedContent
from ai.app.knowledge.documents import DocumentSection


def extract_pdf(raw_bytes: bytes) -> ExtractedContent:
    """Deterministically extract text pages and metadata from PDF bytes."""
    try:
        stream = io.BytesIO(raw_bytes)
        reader = PdfReader(stream)
    except (PdfReadError, Exception) as exc:
        raise ExtractionError(f"Failed to parse PDF binary stream: {exc}") from exc

    page_count = len(reader.pages)
    if page_count == 0:
        raise ExtractionError("PDF document has 0 pages.")

    sections: list[DocumentSection] = []
    full_text_blocks: list[str] = []

    for idx, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:
            page_text = ""

        cleaned_page_text = page_text.strip()
        if cleaned_page_text:
            sections.append(
                DocumentSection(
                    section_id=f"page_{idx}",
                    heading=f"Page {idx}",
                    level=1,
                    content=cleaned_page_text,
                )
            )
            full_text_blocks.append(f"--- Page {idx} ---\n{cleaned_page_text}")

    full_text = "\n\n".join(full_text_blocks).strip()

    if not full_text:
        raise ExtractionError(
            "PDF contains no extractable text layer (document may be empty, encrypted, or a scanned image)."
        )

    # Extract metadata if embedded
    title: str | None = None
    pdf_meta: dict = {}
    if reader.metadata:
        title = reader.metadata.title
        for k, v in reader.metadata.items():
            if isinstance(v, (str, int, float, bool)):
                pdf_meta[str(k).lstrip("/")] = v

    return ExtractedContent(
        title=title,
        raw_text=full_text,
        sections=sections,
        metadata={"extractor": "pypdf_deterministic_v1", "pdf_metadata": pdf_meta},
        page_count=page_count,
    )
