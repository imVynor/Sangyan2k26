"""Deterministic HTML extraction preserving headings, paragraphs, and structure.

Rules:
- Zero LLM rewriting or summarizing.
- Strip scripts, styles, navigation, and noise.
- Extract title from <title> or primary <h1>.
- Group body content into hierarchical DocumentSection structures.
"""

import re
from bs4 import BeautifulSoup, Tag
from ai.app.ingestion.errors import ExtractionError
from ai.app.ingestion.models import ExtractedContent
from ai.app.knowledge.documents import DocumentSection


def extract_html(raw_bytes: bytes, encoding: str = "utf-8") -> ExtractedContent:
    """Extract visible text and heading hierarchy deterministically from HTML bytes."""
    try:
        html_str = raw_bytes.decode(encoding, errors="replace")
    except Exception as exc:
        raise ExtractionError(f"Failed to decode HTML bytes: {exc}") from exc

    soup = BeautifulSoup(html_str, "html.parser")

    # 1. Remove non-content elements and navigational clutter
    for tag in soup(["script", "style", "noscript", "meta", "svg", "nav", "footer", "header"]):
        tag.decompose()

    # 2. Extract title
    title: str | None = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # 3. Extract sections based on heading hierarchy
    body = soup.body or soup
    sections: list[DocumentSection] = []
    
    current_heading: str | None = title
    current_level: int = 1
    current_paras: list[str] = []
    sec_counter = 1

    heading_tags = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

    # Traverse all elements sequentially
    for elem in body.find_all(list(heading_tags.keys()) + ["p", "li", "div"]):
        tag_name = elem.name.lower()
        if tag_name in heading_tags:
            # Commit previous section if it had content
            if current_paras:
                sec_text = "\n\n".join(current_paras).strip()
                if sec_text:
                    sections.append(
                        DocumentSection(
                            section_id=f"sec_{sec_counter}",
                            heading=current_heading,
                            level=current_level,
                            content=sec_text,
                        )
                    )
                    sec_counter += 1
                current_paras = []

            current_heading = elem.get_text(strip=True)
            current_level = heading_tags[tag_name]
        elif tag_name in {"p", "li"}:
            text = elem.get_text(strip=True)
            if text:
                current_paras.append(text)

    # Commit final section
    if current_paras:
        sec_text = "\n\n".join(current_paras).strip()
        if sec_text:
            sections.append(
                DocumentSection(
                    section_id=f"sec_{sec_counter}",
                    heading=current_heading,
                    level=current_level,
                    content=sec_text,
                )
            )

    # Fallback if no sections were built but raw text exists
    full_text = body.get_text(separator="\n", strip=True)
    clean_text = re.sub(r"\n{3,}", "\n\n", full_text)

    if not clean_text:
        raise ExtractionError("HTML document contains no extractable text.")

    if not sections:
        sections.append(
            DocumentSection(
                section_id="sec_root",
                heading=title or "Document Content",
                level=1,
                content=clean_text,
            )
        )

    return ExtractedContent(
        title=title,
        raw_text=clean_text,
        sections=sections,
        metadata={"extractor": "html_deterministic_v1"},
        page_count=None,
    )
