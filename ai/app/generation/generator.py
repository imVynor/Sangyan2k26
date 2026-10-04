"""Auditable Citizen-Facing Response Generator for SANGYAN.

Epistemic foundation:
- Consumes ONLY structured outputs from AssessmentResult, RetrievalResponse, and Evidence.
- Never mutates case facts, evidence, retrieved provisions, or assessment status.
- Generates status-specific explanations adhering to epistemic boundaries.
- Rejects hallucinated citations and unsupported claims via GenerationValidator.
- Communicates objective assessment rather than definitive legal verdicts.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Sequence

from ai.app.assessment.contracts import (
    AssessmentFinding,
    AssessmentResult,
    AssessmentStatus,
    EvidenceItem,
)
from ai.app.generation.citation_renderer import CitationRenderer
from ai.app.generation.contracts import (
    CitationReference,
    GeneratedFinding,
    GeneratedResponse,
)
from ai.app.generation.validator import GenerationValidator
from ai.app.models.provider import LLMProvider
from ai.app.models.schemas import Message
from ai.app.retrieval.contracts import RetrievalResponse

logger = logging.getLogger("sangyan.generation.generator")

DISCLAIMER_TEXT = (
    "DISCLAIMER: SANGYAN provides automated regulatory and procedural assessments based solely on "
    "the evidence supplied and authoritative provisions retrieved from official sources. This output "
    "is informational and does not constitute a formal order, court ruling, or certified legal advice."
)


class AuditableResponseGenerator:
    """Generates structured, citizen-facing explanations from deterministic assessment results."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider

    def generate_response(
        self,
        assessment: AssessmentResult,
        retrieval: RetrievalResponse,
        evidence_items: Sequence[EvidenceItem] | None = None,
        case_facts: dict[str, Any] | None = None,
        clarification_plan: Any = None,
    ) -> GeneratedResponse:
        """Produce an auditable, citizen-facing explanation grounded in assessment and retrieval."""
        ev_list = list(evidence_items or [])
        facts = dict(case_facts or {})

        # 1. Render Official Citations
        citations = CitationRenderer.render_citations(retrieval.results)
        citations_map = {c.provision_id: c for c in citations}

        # 2. Synthesize Evidence Summary
        evidence_summary = self._summarize_evidence(ev_list)

        # 3. Generate Status-Specific Explanation and Findings
        summary, findings, next_steps = self._synthesize_content(
            assessment=assessment,
            retrieval=retrieval,
            citations_map=citations_map,
            facts=facts,
            evidence_summary=evidence_summary,
            clarification_plan=clarification_plan,
        )

        planned_questions = [
            q.question for q in clarification_plan.questions
        ] if clarification_plan and getattr(clarification_plan, "questions", None) else []

        response = GeneratedResponse(
            case_id=assessment.case_id,
            summary=summary,
            assessment_status=assessment.status,
            findings=findings,
            supporting_evidence_summary=evidence_summary,
            regulatory_basis=citations,
            missing_information=assessment.missing_information,
            clarification_questions=planned_questions,
            next_steps=next_steps,
            disclaimers=[DISCLAIMER_TEXT],
            validation_passed=True,
            validation_errors=[],
        )

        # 4. Execute Post-Generation Validation
        val_res = GenerationValidator.validate(response, assessment, retrieval)
        response.validation_passed = val_res.is_valid
        response.validation_errors = val_res.errors

        if not val_res.is_valid:
            logger.error(f"Generation validation failed for case {assessment.case_id}: {val_res.errors}")

        return response

    async def polish_summary(
        self,
        response: GeneratedResponse,
        assessment: AssessmentResult,
        retrieval: RetrievalResponse,
        user_question: str | None,
        language: str = "en",
    ) -> bool:
        """Make the validated assessment easier to read without changing its meaning."""
        if self.llm_provider is None:
            return False

        original_summary = response.summary
        try:
            generated = await self.llm_provider.generate(
                messages=[
                    Message(
                        role="system",
                        content=(
                            "You rewrite financial-grievance assessment text for clarity and empathy. "
                            "Use only the facts and conclusions in the supplied draft. Do not add legal "
                            "advice, causes, promises, amounts, dates, or conclusions. Preserve uncertainty, "
                            "the assessment status, and every requested missing detail. Return only a concise "
                            "plain-text answer in the requested language, in at most 3 sentences."
                        ),
                    ),
                    Message(
                        role="user",
                        content=(
                            f"Language: {language}\n"
                            f"Citizen question or latest reply: {(user_question or 'Not provided')[:1200]}\n"
                            f"Authoritative assessment status: {assessment.status.value}\n"
                            f"Missing information: {', '.join(assessment.missing_information) or 'None'}\n"
                            f"Draft answer to rewrite:\n{original_summary[:2400]}"
                        ),
                    ),
                ],
                temperature=0.2,
                max_tokens=120,
            )
            candidate = generated.content.strip()
            if not candidate or len(candidate) > 1200:
                return False

            response.summary = candidate
            validation = GenerationValidator.validate(response, assessment, retrieval)
            if not validation.is_valid:
                response.summary = original_summary
                logger.warning(
                    "LLM response rewrite rejected for case %s: %s",
                    response.case_id,
                    validation.errors,
                )
                return False
            response.validation_passed = True
            response.validation_errors = []
            return True
        except Exception:
            logger.warning(
                "LLM response rewrite unavailable for case %s; using deterministic answer",
                response.case_id,
                exc_info=True,
            )
            response.summary = original_summary
            return False

    def _summarize_evidence(self, evidence_items: Sequence[EvidenceItem]) -> list[str]:
        """Summarize observed empirical facts into clean human-readable bullets."""
        summary: list[str] = []
        for item in evidence_items:
            summary.append(f"{item.field_name}: {item.value} (Source: {item.source}, Type: {item.evidence_type.value})")
        return summary

    def _synthesize_content(
        self,
        assessment: AssessmentResult,
        retrieval: RetrievalResponse,
        citations_map: dict[str, CitationReference],
        facts: dict[str, Any],
        evidence_summary: list[str],
        clarification_plan: Any = None,
    ) -> tuple[str, list[GeneratedFinding], list[str]]:
        """Synthesize status-specific explanations, findings, and actionable next steps."""
        status = assessment.status
        findings: list[GeneratedFinding] = []
        next_steps: list[str] = []

        # =================================================================
        # 1. VIOLATION_CONFIRMED
        # =================================================================
        if status == AssessmentStatus.VIOLATION_CONFIRMED:
            summary = (
                "Based on the supplied evidence, the charged amount or operational action violates "
                "the binding statutory limits established by official regulatory provisions."
            )
            for f in assessment.findings:
                c_tags = CitationRenderer.format_inline_citations(f.provision_ids, citations_map)
                findings.append(
                    GeneratedFinding(
                        status=status,
                        heading="Regulatory Violation Identified",
                        explanation=f"{f.statement} Governing authority mandate: {c_tags}",
                        cited_provisions=f.provision_ids,
                        cited_evidence=f.evidence_ids,
                    )
                )
            next_steps = [
                "1. Lodge a written grievance with the intermediary's Compliance Officer citing the above provision.",
                "2. If unresolved within 30 days, escalate the complaint to SEBI SCORES 2.0 (scores.gov.in).",
                "3. Alternatively, file an online conciliation/arbitration request on the SMART ODR portal (smartodr.in).",
            ]

        # =================================================================
        # 2. COMPLIANT_WITH_REGULATION
        # =================================================================
        elif status == AssessmentStatus.COMPLIANT_WITH_REGULATION:
            summary = (
                "Based on the evaluated provisions, the observed charges and intermediary procedures "
                "fall strictly within the permissible parameters established by regulatory guidelines."
            )
            for f in assessment.findings:
                c_tags = CitationRenderer.format_inline_citations(f.provision_ids, citations_map)
                findings.append(
                    GeneratedFinding(
                        status=status,
                        heading="Statutory Compliance Established",
                        explanation=f"{f.statement} Verified against: {c_tags}",
                        cited_provisions=f.provision_ids,
                        cited_evidence=f.evidence_ids,
                    )
                )
            next_steps = [
                "No regulatory non-compliance was identified under the evaluated rules.",
                "If you believe specific contractual terms were miscalculated, verify the itemized contract note against the broker's declared tariff schedule.",
            ]

        # =================================================================
        # 3. ORGANISATION_POLICY_DEVIATION
        # =================================================================
        elif status == AssessmentStatus.ORGANISATION_POLICY_DEVIATION:
            summary = (
                "While the action does not necessarily breach the overarching regulatory ceiling, "
                "the intermediary deviated from its own publicly declared tariff schedule or operational procedures."
            )
            for f in assessment.findings:
                c_tags = CitationRenderer.format_inline_citations(f.provision_ids, citations_map)
                findings.append(
                    GeneratedFinding(
                        status=status,
                        heading="Intermediary Policy Deviation",
                        explanation=f"{f.statement} Published schedule: {c_tags}",
                        cited_provisions=f.provision_ids,
                        cited_evidence=f.evidence_ids,
                    )
                )
            next_steps = [
                "1. Contact the broker's customer support and request an immediate ledger adjustment/refund citing their published tariff schedule.",
                "2. Escalate to the intermediary's internal Grievance Redressal Officer if uncorrected.",
            ]

        # =================================================================
        # 4. EVIDENCE_INSUFFICIENT
        # =================================================================
        elif status == AssessmentStatus.EVIDENCE_INSUFFICIENT:
            missing_str = ", ".join(assessment.missing_information) if assessment.missing_information else "essential details"
            if clarification_plan and getattr(clarification_plan, "questions", None):
                q_text_list = [q.question for q in clarification_plan.questions]
                q_why_list = [f"{q.field}: {q.reason}" for q in clarification_plan.questions]
                summary = (
                    "Current finding: Cannot determine whether the fee/charge is legally permissible. "
                    f"Additional evidentiary clarification is required: {missing_str}."
                )
                findings.append(
                    GeneratedFinding(
                        status=status,
                        heading="Additional Evidence Required",
                        explanation=(
                            f"The rules governing this grievance require explicit factual parameters: {missing_str}.\n"
                            "What I need:\n" + "\n".join([f"- {q}" for q in q_text_list]) + "\n"
                            "Why:\n" + "\n".join([f"- {w}" for w in q_why_list])
                        ),
                        cited_provisions=[],
                        cited_evidence=[],
                    )
                )
                next_steps = [
                    f"Please clarify: {q}" for q in q_text_list
                ]
            else:
                summary = (
                    f"The assessment cannot be deterministically completed because essential evidentiary information "
                    f"is currently missing or contradicted: {missing_str}."
                )
                findings.append(
                    GeneratedFinding(
                        status=status,
                        heading="Additional Evidence Required",
                        explanation=(
                            f"The rules governing this grievance require explicit factual parameters: {missing_str}. "
                            "Without verified documentation of these facts, a conclusive legal assessment cannot be rendered."
                        ),
                        cited_provisions=[],
                        cited_evidence=[],
                    )
                )
                next_steps = [
                    f"Please provide supporting documentation for: {missing_str} (e.g. Contract Note, Holding Statement, Ledger Statement).",
                ]

        # =================================================================
        # 5. TEMPORALITY_UNRESOLVED
        # =================================================================
        elif status == AssessmentStatus.TEMPORALITY_UNRESOLVED:
            summary = (
                "Relevant statutory provisions were identified, but historical temporal applicability "
                "could not be established for the specific date of this incident."
            )
            findings.append(
                GeneratedFinding(
                    status=status,
                    heading="Temporal Applicability Ambiguous",
                    explanation=(
                        "Regulatory regimes change over time. The available circulars could not be proven "
                        "to be legally operative at the time the transaction took place."
                    ),
                    cited_provisions=[r.provision_id for r in retrieval.results[:2]],
                    cited_evidence=[],
                )
            )
            next_steps = [
                "Confirm the exact transaction or incident date from official bank/demat statements.",
                "Retrieve archived circulars governing the relevant historical timeline.",
            ]

        # =================================================================
        # 6. REGULATORY_COVERAGE_UNRESOLVED
        # =================================================================
        elif status == AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED:
            summary = (
                "Authoritative regulatory provisions directly governing this specific subject matter "
                "were not found in the current regulatory repository. No regulatory conclusion is asserted."
            )
            findings.append(
                GeneratedFinding(
                    status=status,
                    heading="Regulatory Coverage Unresolved",
                    explanation=(
                        "While intermediary policies or FAQs may exist, authoritative regulatory mandates "
                        "(e.g. from SEBI, Exchange bylaws) could not be retrieved for this dispute domain."
                    ),
                    cited_provisions=[],
                    cited_evidence=[],
                )
            )
            next_steps = [
                "Review the intermediary's terms of service and submit an inquiry through their help desk.",
            ]

        # =================================================================
        # 7. CONFLICTING_PROVISIONS
        # =================================================================
        elif status == AssessmentStatus.CONFLICTING_PROVISIONS:
            summary = (
                "Multiple applicable provisions were retrieved with contradictory mandates, and the conflict "
                "could not be deterministically resolved through authority hierarchy or temporal precedence."
            )
            for c in assessment.conflicts:
                findings.append(
                    GeneratedFinding(
                        status=status,
                        heading="Contradictory Normative Provisions",
                        explanation=f"Conflict detected: {c.nature_of_conflict}. Explanation: {c.explanation}",
                        cited_provisions=c.provision_ids,
                        cited_evidence=[],
                    )
                )
            next_steps = [
                "Seek formal legal clarification regarding which competing instrument governs this specific account.",
            ]

        # =================================================================
        # Default / Fallback
        # =================================================================
        else:
            summary = f"Assessment completed with status: {status.value}."
            findings.append(
                GeneratedFinding(
                    status=status,
                    heading="Assessment Status",
                    explanation=f"Evaluation concluded with status {status.value}.",
                    cited_provisions=[],
                    cited_evidence=[],
                )
            )
            next_steps = ["Review the assessment details."]

        return summary, findings, next_steps
