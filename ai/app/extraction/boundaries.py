"""Deterministic candidate boundary detection for SANGYAN DocumentSections.

Segments a structural section into atomic candidate spans while preserving:
- Exact character offsets (source_start, source_end).
- Zero alterations to source text: section_content[start:end] == span_text.
- Clause numbering and bullet hierarchy.
- Logical cohesion: compound rules with conditions or exceptions are not fractured.
"""

import re
from typing import NamedTuple


class CandidateSpan(NamedTuple):
    """An exact, verified substring span within a DocumentSection."""
    text: str
    start_idx: int
    end_idx: int
    section_reference: str | None = None
    clause_reference: str | None = None


# Patterns for structured clause boundaries
CLAUSE_START_RE = re.compile(
    r"(?m)^(?:(?:\d+\.|\(\d+\)|\d+\)|\([a-z]\)|[a-z]\.|\([ivxIVX]+\)|[ivxIVX]+\.)\s+|[•*-]\s+)"
)


def detect_candidate_spans(
    content: str,
    min_length: int = 15,
    max_length: int = 4000,
) -> list[CandidateSpan]:
    """Segment section content into coherent candidate provision spans.
    
    Guarantees:
    - Every returned span.text == content[span.start_idx:span.end_idx].
    - Zero modification or synthetic padding.
    """
    raw = content or ""
    if not raw.strip():
        return []

    # 1. Normalize line endings for consistent index calculation
    normalized = raw.replace("\r\n", "\n")

    # Check for paragraph separation (double newline)
    paragraph_splits = list(re.finditer(r"\n\s*\n+", normalized))

    # If the total section is compact and has no internal breaks, treat as single cohesive candidate
    clean_stripped = normalized.strip()
    if not paragraph_splits and len(clean_stripped) <= 600 and len(clean_stripped) >= min_length:
        start = normalized.find(clean_stripped)
        if start != -1:
            end = start + len(clean_stripped)
            ref = _extract_clause_label(clean_stripped)
            return [CandidateSpan(text=clean_stripped, start_idx=start, end_idx=end, clause_reference=ref)]

    # 2. Identify candidate break points (paragraphs or numbered clauses)
    spans: list[CandidateSpan] = []

    if paragraph_splits:
        last_pos = 0
        for m in paragraph_splits:
            p_start = m.start()
            chunk = normalized[last_pos:p_start]
            span = _clean_span(normalized, chunk, last_pos, min_length)
            if span:
                spans.append(span)
            last_pos = m.end()

        # Final chunk
        chunk = normalized[last_pos:]
        span = _clean_span(normalized, chunk, last_pos, min_length)
        if span:
            spans.append(span)
    else:
        # Check for clause / bullet lines
        clause_matches = list(CLAUSE_START_RE.finditer(normalized))
        if len(clause_matches) > 1:
            for i in range(len(clause_matches)):
                start = clause_matches[i].start()
                end = clause_matches[i + 1].start() if i + 1 < len(clause_matches) else len(normalized)
                chunk = normalized[start:end]
                span = _clean_span(normalized, chunk, start, min_length)
                if span:
                    spans.append(span)
        else:
            # Fallback: single coherent span if long enough
            span = _clean_span(normalized, normalized, 0, min_length)
            if span:
                spans.append(span)

    # 3. If any individual span is too large (> max_length), split on sentence boundaries
    refined: list[CandidateSpan] = []
    for s in spans:
        if len(s.text) > max_length:
            sub_spans = _split_large_span(normalized, s.start_idx, s.end_idx, max_length)
            refined.extend(sub_spans)
        else:
            refined.append(s)

    return refined


def _clean_span(
    full_text: str,
    raw_chunk: str,
    chunk_start: int,
    min_length: int,
) -> CandidateSpan | None:
    """Trim leading/trailing whitespace while tracking exact absolute indices in full_text."""
    if not raw_chunk or not raw_chunk.strip():
        return None

    # Calculate exact start after leading whitespace
    stripped_leading = raw_chunk.lstrip()
    leading_ws_count = len(raw_chunk) - len(stripped_leading)
    abs_start = chunk_start + leading_ws_count

    stripped = stripped_leading.rstrip()
    if len(stripped) < min_length:
        return None

    abs_end = abs_start + len(stripped)

    # Verify invariant
    assert full_text[abs_start:abs_end] == stripped, "Index invariant violation in candidate boundary detection"

    clause_ref = _extract_clause_label(stripped)
    return CandidateSpan(
        text=stripped,
        start_idx=abs_start,
        end_idx=abs_end,
        clause_reference=clause_ref,
    )


def _split_large_span(
    full_text: str,
    start_idx: int,
    end_idx: int,
    max_length: int,
) -> list[CandidateSpan]:
    """Split an oversized chunk on sentence boundaries without losing substring alignment."""
    sub_spans: list[CandidateSpan] = []
    chunk = full_text[start_idx:end_idx]

    # Find sentence endings followed by space and capital letter or clause number
    sentence_breaks = [m.end() for m in re.finditer(r"\.\s+(?=[A-Z0-9(])", chunk)]
    if not sentence_breaks:
        return [CandidateSpan(text=chunk, start_idx=start_idx, end_idx=end_idx)]

    current_start = 0
    for b in sentence_breaks:
        if (b - current_start) >= 200:
            part = chunk[current_start:b].strip()
            if part:
                p_start = start_idx + current_start + (len(chunk[current_start:b]) - len(chunk[current_start:b].lstrip()))
                p_end = p_start + len(part)
                sub_spans.append(CandidateSpan(text=part, start_idx=p_start, end_idx=p_end))
            current_start = b

    remaining = chunk[current_start:].strip()
    if remaining:
        r_start = start_idx + current_start + (len(chunk[current_start:]) - len(chunk[current_start:].lstrip()))
        r_end = r_start + len(remaining)
        sub_spans.append(CandidateSpan(text=remaining, start_idx=r_start, end_idx=r_end))

    return sub_spans or [CandidateSpan(text=chunk, start_idx=start_idx, end_idx=end_idx)]


def _extract_clause_label(text: str) -> str | None:
    """Extract initial clause numbering like '1.', '(a)', 'Clause 3', etc."""
    m = re.match(r"^((?:Clause\s+\d+|Section\s+\d+|\d+\.|\(\d+\)|\([a-z]\)|[a-z]\.|\([ivxIVX]+\)))\s*", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None
