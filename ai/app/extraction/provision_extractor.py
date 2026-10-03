"""Provision extraction implementations: deterministic and LLM-assisted."""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Sequence

from ai.app.extraction.boundaries import detect_candidate_spans
from ai.app.extraction.rules import (
    classify_provision_type,
    extract_conditions,
    extract_cross_references,
    extract_definitions,
    extract_exceptions,
    extract_fees,
    extract_procedures,
    extract_timelines,
)
from ai.app.knowledge.provisions import Provision, ProvisionType
from ai.app.knowledge.source_classes import SourceClass
from ai.app.models.provider import LLMProvider

logger = logging.getLogger(__name__)


def generate_deterministic_provision_id(
    document_id: str,
    section_key: str,
    clause_ref: str | int | None,
    source_text: str,
) -> str:
    """Generate reproducible deterministic provision ID using SHA-256."""
    seed = f"{document_id}:{section_key}:{clause_ref}:{source_text[:128]}"
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    safe_sec = section_key.replace("/", "_").replace("-", "_")[:24]
    return f"prov_{document_id}_{safe_sec}_{h}"


class ProvisionExtractor(ABC):
    """Abstract base class for extracting provisions from document sections."""

    @abstractmethod
    async def extract_provisions(
        self,
        section_key: str,
        section_heading: str | None,
        section_content: str,
        document_id: str,
        authority: str | None,
        organisation_id: str | None,
        source_class: SourceClass,
        canonical_url: str | None = None,
        source_hash: str | None = None,
        parent_topics: list[str] | None = None,
    ) -> list[Provision]:
        """Extract provisions from a section's text."""
        pass


class DeterministicProvisionExtractor(ProvisionExtractor):
    """Deterministic extractor preserving exact source spans and applying rule-based parsers."""

    async def extract_provisions(
        self,
        section_key: str,
        section_heading: str | None,
        section_content: str,
        document_id: str,
        authority: str | None,
        organisation_id: str | None,
        source_class: SourceClass,
        canonical_url: str | None = None,
        source_hash: str | None = None,
        parent_topics: list[str] | None = None,
    ) -> list[Provision]:
        content = section_content or ""
        if not content.strip():
            return []

        spans = detect_candidate_spans(content)
        if not spans:
            clean = content.strip()
            start = content.find(clean)
            if start != -1:
                from ai.app.extraction.boundaries import CandidateSpan
                spans = [CandidateSpan(text=clean, start_idx=start, end_idx=start + len(clean))]
            else:
                return []

        provisions: list[Provision] = []
        for i, span in enumerate(spans, start=1):
            prov_type = classify_provision_type(span.text, heading=section_heading, source_class=source_class)
            conditions = extract_conditions(span.text)
            exceptions = extract_exceptions(span.text)
            procedures = extract_procedures(span.text)
            timelines = extract_timelines(span.text)
            definitions = extract_definitions(span.text)
            cross_refs = extract_cross_references(span.text)
            fees = extract_fees(span.text)

            prov_id = generate_deterministic_provision_id(
                document_id=document_id,
                section_key=section_key,
                clause_ref=span.clause_reference or i,
                source_text=span.text,
            )

            prov = Provision(
                provision_id=prov_id,
                document_id=document_id,
                section_id=section_key,
                provision_type=prov_type,
                source_text=span.text,
                source_start=span.start_idx,
                source_end=span.end_idx,
                authority=authority,
                organisation_id=organisation_id,
                source_class=source_class,
                canonical_url=canonical_url,
                source_hash=source_hash,
                conditions=conditions,
                exceptions=exceptions,
                procedures=procedures,
                timelines=timelines,
                definitions=definitions,
                cross_references=cross_refs,
                fees_or_charges=fees,
                topic=parent_topics or [],
            )
            provisions.append(prov)

        return provisions


class LLMProvisionExtractor(ProvisionExtractor):
    """LLM-assisted extractor with strict deterministic fallback on any validation failure."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider
        self.fallback = DeterministicProvisionExtractor()

    async def extract_provisions(
        self,
        section_key: str,
        section_heading: str | None,
        section_content: str,
        document_id: str,
        authority: str | None,
        organisation_id: str | None,
        source_class: SourceClass,
        canonical_url: str | None = None,
        source_hash: str | None = None,
        parent_topics: list[str] | None = None,
    ) -> list[Provision]:
        if not self.provider:
            return await self.fallback.extract_provisions(
                section_key=section_key,
                section_heading=section_heading,
                section_content=section_content,
                document_id=document_id,
                authority=authority,
                organisation_id=organisation_id,
                source_class=source_class,
                canonical_url=canonical_url,
                source_hash=source_hash,
                parent_topics=parent_topics,
            )

        try:
            prompt = (
                f"Extract regulatory provisions from the following text.\n"
                f"Document: {document_id}\nSection: {section_key}\nHeading: {section_heading or 'None'}\n\n"
                f"Content:\n{section_content}\n\n"
                f"Return JSON object with 'provisions': list of objects with 'source_text' (verbatim substring) and 'provision_type'."
            )
            response = await self.provider.generate(
                prompt=prompt,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.content)
            raw_items = data.get("provisions", [])
            provisions: list[Provision] = []

            for i, item in enumerate(raw_items, start=1):
                src = item.get("source_text", "")
                if not src or src not in section_content:
                    # Hallucination or altered text detected -> trigger fallback
                    raise ValueError(f"Extracted source_text is not a verbatim substring of section content: '{src[:30]}...'")

                start = section_content.find(src)
                end = start + len(src)
                pt_str = item.get("provision_type", "RULE")
                try:
                    pt = ProvisionType(pt_str)
                except Exception:
                    pt = ProvisionType.RULE

                prov_id = generate_deterministic_provision_id(
                    document_id=document_id,
                    section_key=section_key,
                    clause_ref=i,
                    source_text=src,
                )

                provisions.append(
                    Provision(
                        provision_id=prov_id,
                        document_id=document_id,
                        section_id=section_key,
                        provision_type=pt,
                        source_text=src,
                        source_start=start,
                        source_end=end,
                        authority=authority,
                        organisation_id=organisation_id,
                        source_class=source_class,
                        canonical_url=canonical_url,
                        source_hash=source_hash,
                        conditions=extract_conditions(src),
                        exceptions=extract_exceptions(src),
                        procedures=extract_procedures(src),
                        timelines=extract_timelines(src),
                        definitions=extract_definitions(src),
                        cross_references=extract_cross_references(src),
                        fees_or_charges=extract_fees(src),
                        topic=parent_topics or [],
                    )
                )

            if not provisions:
                return await self.fallback.extract_provisions(
                    section_key=section_key,
                    section_heading=section_heading,
                    section_content=section_content,
                    document_id=document_id,
                    authority=authority,
                    organisation_id=organisation_id,
                    source_class=source_class,
                    canonical_url=canonical_url,
                    source_hash=source_hash,
                    parent_topics=parent_topics,
                )
            return provisions

        except Exception as exc:
            logger.warning("LLM provision extraction failed, falling back to deterministic: %s", exc)
            return await self.fallback.extract_provisions(
                section_key=section_key,
                section_heading=section_heading,
                section_content=section_content,
                document_id=document_id,
                authority=authority,
                organisation_id=organisation_id,
                source_class=source_class,
                canonical_url=canonical_url,
                source_hash=source_hash,
                parent_topics=parent_topics,
            )
