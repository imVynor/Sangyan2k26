"""Context Builder for Downstream SANGYAN Reasoning and Rule Assessment.

Epistemic foundation:
- Epistemic boundary: separates retrieved authoritative evidence from user case assertions.
- Compact, structured format: includes only top relevant provisions, preserving citation,
  temporal status, authority, and source class.
- Explicit failure annotations prevent reasoning models from hallucinating ungrounded rules.
"""

from typing import Sequence
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult


class ContextBuilder:
    """Builds structured, provenance-preserving evidence contexts for LLM assessment."""

    def build_evidence_context(
        self,
        response: RetrievalResponse,
        max_provisions: int = 8,
    ) -> str:
        """Render retrieved provisions into an authoritative markdown evidence block."""
        if not response.results:
            reasons = ", ".join(r.value for r in response.failure_reasons) or "NO_RELEVANT_PROVISIONS"
            return (
                "### AUTHORITATIVE REGULATORY & ORGANISATION EVIDENCE\n\n"
                f"> **RETRIEVAL STATUS**: FAILED ({reasons})\n"
                "> No authoritative provisions met the required relevance or applicability thresholds.\n"
                "> Epistemic rule: Do NOT fabricate or assume regulatory rules in the absence of evidence."
            )

        lines: list[str] = [
            "### AUTHORITATIVE REGULATORY & ORGANISATION EVIDENCE",
            f"*Total Provisions Retrieved*: {len(response.results)} | *Active Regulators*: {', '.join(response.routed_authorities) or 'N/A'}\n",
        ]

        for r in response.results[:max_provisions]:
            owner = r.authority or r.organisation_id or "Regulatory Source"
            lines.append(f"#### [{r.rank}] {owner} — {r.provision_type} (`{r.provision_id}`)")
            lines.append(f"- **Citation**: {r.citation}")
            lines.append(f"- **Source Class**: `{r.source_class}` | **Source URL**: [{r.source_url}]({r.source_url})")
            lines.append(f"- **Temporal Applicability**: `{r.applicability_status}` (State: `{r.temporal_status}`)")
            lines.append(f"- **Relevance Score**: `{r.relevance_score:.3f}` (Methods: `{', '.join(r.retrieval_methods)}`)")
            if r.section_reference:
                lines.append(f"- **Reference**: Section `{r.section_reference}`" + (f", Clause `{r.clause_reference}`" if r.clause_reference else ""))
            lines.append("\n```text")
            lines.append(r.provision_text.strip())
            lines.append("```\n")

        lines.append(
            "> [!NOTE]\n"
            "> Epistemic Invariant: The above provisions are verbatim official texts. "
            "Evaluate claims and obligations strictly against these explicit sources."
        )

        return "\n".join(lines)
