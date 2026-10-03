"""Deterministic document format classification.

Classifies incoming payloads based strictly on Content-Type headers, URL extensions,
and magic bytes. Zero LLM involvement.
"""

from enum import Enum
from urllib.parse import urlparse


class DocumentFormat(str, Enum):
    """Supported document binary/text formats."""
    HTML = "HTML"
    PDF = "PDF"
    UNSUPPORTED = "UNSUPPORTED"


def classify_document(
    content_type: str | None,
    raw_bytes: bytes,
    url: str | None = None,
) -> DocumentFormat:
    """Deterministically classify document format without probabilistic inference.
    
    Checks in order:
    1. Magic bytes in content prefix (%PDF- for PDF).
    2. HTTP Content-Type header (application/pdf, text/html).
    3. URL path extension (.pdf, .html, .htm).
    """
    # 1. Inspect magic bytes first (most reliable against misconfigured server headers)
    prefix = raw_bytes[:1024].lstrip()
    if prefix.startswith(b"%PDF-"):
        return DocumentFormat.PDF

    # 2. Inspect Content-Type header
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct == "application/pdf":
        return DocumentFormat.PDF
    if ct in {"text/html", "application/xhtml+xml"}:
        return DocumentFormat.HTML

    # 3. Check HTML markup presence if content_type is ambiguous or text/plain
    if (
        prefix.lower().startswith(b"<!doctype html")
        or prefix.lower().startswith(b"<html")
        or b"<body" in prefix.lower()
    ):
        return DocumentFormat.HTML

    # 4. Check URL extension as fallback
    if url:
        path = urlparse(url).path.lower()
        if path.endswith(".pdf"):
            return DocumentFormat.PDF
        if path.endswith((".html", ".htm", ".xhtml")):
            return DocumentFormat.HTML

    return DocumentFormat.UNSUPPORTED
