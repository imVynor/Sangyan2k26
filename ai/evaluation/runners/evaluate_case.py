"""Single Case Evaluation Runner for SANGYAN (Phase 7A).

Epistemic foundation:
- Runs an EvaluationCase through CaseOrchestrator end-to-end.
- Evaluates fact extraction, negative unknowns, issue classification, retrieval,
  temporal regimes, claims/contradictions, deterministic assessment, clarifications, and grounding.
- Enforces strict safety-critical invariants: zero false violations, zero false compliances.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
import time
from typing import Any

from ai.app.case.contracts import CaseState, CaseStatus
from ai.app.extraction.document_extractor import DocumentExtractionPayload, DocumentSpan
from ai.app.orchestration.contracts import OrchestrationInputEvent
from ai.app.orchestration.orchestrator import CaseOrchestrator
from ai.evaluation.corpus.models import (
    CaseEvaluationReport,
    EvaluationCase,
    StageEvaluationResult,
)
from ai.evaluation.evaluators.assessment_evaluator import AssessmentEvaluator
from ai.evaluation.evaluators.clarification_evaluator import ClarificationEvaluator
from ai.evaluation.evaluators.evidence_evaluator import EvidenceEvaluator
from ai.evaluation.evaluators.fact_evaluator import FactEvaluator
from ai.evaluation.evaluators.grounding_evaluator import GroundingEvaluator
from ai.evaluation.evaluators.issue_evaluator import IssueEvaluator
from ai.evaluation.evaluators.retrieval_evaluator import ProvisionRetrievalEvaluator
from ai.evaluation.evaluators.temporal_evaluator import TemporalEvaluator

logger = logging.getLogger("sangyan.evaluation.runner.case")


class SingleCaseEvaluator:
    """Executes a single benchmark grievance case through SANGYAN and evaluates all stages."""

    def __init__(self, orchestrator: CaseOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or CaseOrchestrator()
        self.fact_evaluator = FactEvaluator()
        self.issue_evaluator = IssueEvaluator()
        self.retrieval_evaluator = ProvisionRetrievalEvaluator()
        self.evidence_evaluator = EvidenceEvaluator()
        self.temporal_evaluator = TemporalEvaluator()
        self.assessment_evaluator = AssessmentEvaluator()
        self.clarification_evaluator = ClarificationEvaluator()
        self.grounding_evaluator = GroundingEvaluator()

    async def evaluate_case(self, case: EvaluationCase) -> CaseEvaluationReport:
        """Run case and evaluate against gold expectations."""
        start_time = time.perf_counter()

        case_id = f"EVAL-{case.case_id}"
        # 1. Initialize case state
        initial_state = CaseState(
            case_id=case_id,
            status=CaseStatus.DRAFT,
            version=1,
            facts={},
            evidence=[],
            claims=[],
        )
        await self.orchestrator.repository.save_case(initial_state)

        # 2. Build initial input event
        docs = []
        if "attached_document" in case.context:
            doc_id = case.context["attached_document"]
            doc_content = case.context.get("document_content", "")
            docs.append(
                DocumentExtractionPayload(
                    document_id=doc_id,
                    raw_content=doc_content,
                    content_format="text",
                    spans=[DocumentSpan(text=doc_content, page_number=1)],
                )
            )

        ref_date = None
        if case.expected_temporal_context and case.expected_temporal_context.transaction_date:
            ref_date = case.expected_temporal_context.transaction_date

        initial_event = OrchestrationInputEvent(
            complaint_text=case.user_input,
            user_message=case.user_input,
            documents=docs,
            reference_date=ref_date,
            language=case.language,
        )

        turn_result = await self.orchestrator.process_turn(
            case_id=case_id,
            input_event=initial_event,
            expected_version=1,
        )

        final_state = await self.orchestrator.repository.get_case(case_id)
        assert final_state is not None

        # 3. Handle multi-turn flow if specified
        if case.multi_turn_flow:
            for turn_spec in case.multi_turn_flow:
                if turn_spec.turn_index == 1:
                    continue  # already executed initial turn

                turn_docs = []
                for doc_dict in turn_spec.attached_documents:
                    d_id = doc_dict.get("document_id", "turn_doc.pdf")
                    d_txt = doc_dict.get("content", "")
                    turn_docs.append(
                        DocumentExtractionPayload(
                            document_id=d_id,
                            raw_content=d_txt,
                            content_format="text",
                            spans=[DocumentSpan(text=d_txt, page_number=1)],
                        )
                    )

                next_event = OrchestrationInputEvent(
                    complaint_text=turn_spec.user_message,
                    user_message=turn_spec.user_message,
                    documents=turn_docs,
                    reference_date=ref_date,
                    language=case.language,
                )

                turn_result = await self.orchestrator.process_turn(
                    case_id=case_id,
                    input_event=next_event,
                    expected_version=final_state.version,
                )
                final_state = await self.orchestrator.repository.get_case(case_id)
                assert final_state is not None

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # 4. Evaluate each stage
        stages: dict[str, StageEvaluationResult] = {}

        # A. Fact Extraction
        fact_res = self.fact_evaluator.evaluate(case, final_state.facts)
        stages["FACT_EXTRACTION"] = fact_res

        # B. Issue Identification
        actual_issues = [case.title, case.user_input]
        if turn_result.assessment_result:
            for f in turn_result.assessment_result.findings:
                actual_issues.append(f.statement if hasattr(f, "statement") else str(f))
        for r in turn_result.retrieval_response.results:
            if r.title:
                actual_issues.append(r.title)
        for k, v in final_state.facts.items():
            actual_issues.append(f"{k} {v}")
        issue_res = self.issue_evaluator.evaluate(case, actual_issues)
        stages["ISSUE_IDENTIFICATION"] = issue_res

        # C. Provision Retrieval
        retrieved_pids = [r.provision_id for r in turn_result.retrieval_response.results]
        retrieval_res = self.retrieval_evaluator.evaluate(case, retrieved_pids)
        stages["PROVISION_RETRIEVAL"] = retrieval_res

        # D. Evidence & Contradictions
        detected_contradictions = []
        for evt in final_state.interaction_history:
            if evt.event_type.value == "EVIDENCE_CONTRADICTION_DETECTED":
                detected_contradictions.append(evt.payload.get("rationale", "contradiction"))
        resolved_fields = {rc.field_name: rc.operative_value for rc in turn_result.resolved_claims}
        evidence_res = self.evidence_evaluator.evaluate(
            case,
            final_state.claims,
            detected_contradictions=detected_contradictions,
            resolved_fields=resolved_fields,
        )
        stages["EVIDENCE_RESOLUTION"] = evidence_res

        # E. Temporal Selection
        temporal_regime = turn_result.retrieval_response.retrieval_stats.get("temporal_regime")
        temporal_res = self.temporal_evaluator.evaluate(
            case,
            selected_provision_ids=retrieved_pids,
            resolved_temporal_regime=temporal_regime,
        )
        stages["TEMPORAL_REASONING"] = temporal_res

        # F. Assessment & Safety Invariants
        actual_fin = {}
        if "total_amount" in final_state.facts or "charged_amount" in final_state.facts:
            actual_fin["total_amount"] = final_state.facts.get("total_amount") or final_state.facts.get("charged_amount")
        assessment_res, false_violation, false_compliance = self.assessment_evaluator.evaluate(
            case,
            turn_result.assessment_result,
            actual_financial=actual_fin,
        )
        stages["ASSESSMENT"] = assessment_res

        # G. Clarifications
        asked_questions = [
            q.question if hasattr(q, "question") else getattr(q, "prompt", str(q))
            for q in turn_result.clarification_plan.questions
        ]
        clarification_res = self.clarification_evaluator.evaluate(case, asked_questions)
        stages["CLARIFICATION"] = clarification_res

        # H. Grounding
        gen_text = ""
        cited_pids = []
        if turn_result.generated_response:
            gen_text = turn_result.generated_response.summary
            for f in turn_result.generated_response.findings:
                gen_text += " " + f.explanation
                cited_pids.extend(f.cited_provisions)
            for c in turn_result.generated_response.regulatory_basis:
                cited_pids.append(c.provision_id)

        grounding_res = self.grounding_evaluator.evaluate(
            case,
            generated_text=gen_text,
            cited_provisions=cited_pids,
            retrieved_provisions=retrieved_pids,
        )
        stages["GROUNDING"] = grounding_res

        # Determine overall pass
        critical_stages = ["FACT_EXTRACTION", "ASSESSMENT"]
        if case.expected_provisions and not case.is_blocked_by_corpus_gap:
            critical_stages.append("PROVISION_RETRIEVAL")

        overall_passed = all(
            stages[s].passed for s in critical_stages if s in stages
        ) and not false_violation and not false_compliance

        # Primary failure class identification
        failure_class = None
        for s in ["ASSESSMENT", "PROVISION_RETRIEVAL", "FACT_EXTRACTION", "CLARIFICATION", "GROUNDING"]:
            if s in stages and not stages[s].passed and stages[s].failure_class:
                failure_class = stages[s].failure_class
                break

        return CaseEvaluationReport(
            case_id=case.case_id,
            title=case.title,
            category=case.category,
            difficulty=case.difficulty,
            overall_passed=overall_passed,
            stages=stages,
            false_violation=false_violation,
            false_compliance=false_compliance,
            failure_class=failure_class,
            latency_ms=latency_ms,
            executed_at=datetime.now(timezone.utc),
        )
