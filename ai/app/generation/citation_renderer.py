"""Citation Renderer and Formatter for SANGYAN Response Generation.

Epistemic foundation:
- Renders structured citation metadata into unambiguous authoritative references.
- Formats instrument identifiers, section numbers, and canonical URLs.
- Never asks LLM to invent or hallucinate citation identifiers.
"""

from typing import Sequence

from ai.app.generation.contracts import CitationReference
from ai.app.retrieval.contracts import RetrievalResult


class CitationRenderer:
    """Renders authoritative citations for retrieved provisions."""

    @staticmethod
    def render_citations(
        results: Sequence[RetrievalResult],
    ) -> list[CitationReference]:
        """Convert a sequence of RetrievalResults into formal CitationReference objects."""
        citations: list[CitationReference] = []
        seen: set[str] = set()

        for res in results:
            if res.provision_id in seen:
                continue
            seen.add(res.provision_id)

            auth = res.authority or res.organisation_id or "Authority"
            sec = res.section_reference or res.clause_reference or res.section_id or ""
            doc_id = res.document_id

            # Compose citation text
            citation_parts = [auth, res.citation]
            if sec:
                citation_parts.append(f"Section/Clause: {sec}")
            citation_text = " | ".join(citation_parts)

            citations.append(
                CitationReference(
                    provision_id=res.provision_id,
                    authority=auth,
                    document_identifier=doc_id,
                    section_clause=sec if sec else None,
                    source_url=res.source_url,
                    citation_text=f"[{citation_text}]",
                    is_validated=True,
                )
            )

        return citations

    @staticmethod
    def format_inline_citations(
        provision_ids: Sequence[str],
        citations_map: dict[str, CitationReference],
    ) -> str:
        """Format inline bracketed citation tags for a list of provision IDs."""
        tags = []
        for pid in provision_ids:
            if pid in citations_map:
                tags.append(citations_map[pid].citation_text)
            else:
                tags.append(f"[{pid}]")
        return " ".join(tags)
