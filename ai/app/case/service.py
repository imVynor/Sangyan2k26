"""Case Service and Multi-Turn Evidentiary Dialogue Coordinator for SANGYAN.

Epistemic foundation:
- Coordinates multi-turn dialogue while preserving immutable case state and audit history.
- Enforces optimistic concurrency (expected_version vs current_version).
- Enforces idempotency via idempotency_key checks.
- Fact extraction proposals pass through the CaseIntegrator / EvidenceManager boundary.
- Evaluates reassessments deterministically and records explicit AssessmentDeltas.
- Plans targeted, minimum-burden clarification questions (ClarificationPlanner).
- Validates that questions target genuine evidentiary gaps (QuestionValidator).
"""

from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Sequence
import uuid

from ai.app.assessment.contracts import (
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceRequirementStatus,
    EvidenceType,
)
from ai.app.assessment.engine import DefaultAssessmentEngine
from ai.app.assessment.evidence_manager import EvidenceManager
from ai.app.case.contracts import (
    AssessmentDelta,
    AssessmentSnapshot,
    CaseEvent,
    CaseEventType,
    CaseState,
    CaseStatus,
    CaseVersionConflictError,
)
from ai.app.case.repository import CaseRepository, InMemoryCaseRepository
from ai.app.clarification.contracts import (
    ClarificationPlan,
    ClarificationPlanStatus,
    ClarificationQuestion,
)
from ai.app.clarification.planner import ClarificationPlanner
from ai.app.clarification.validator import QuestionValidator
from ai.app.extraction.case_integrator import CaseIntegrator
from ai.app.extraction.contracts import FactExtractionRequest
from ai.app.extraction.document_extractor import DocumentExtractionPayload
from ai.app.extraction.extractor import FactExtractor
from ai.app.generation.contracts import GeneratedResponse
from ai.app.generation.generator import AuditableResponseGenerator
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult

logger = logging.getLogger("sangyan.case.service")


class CaseService:
    """Coordinates iterative case reasoning, multi-turn dialogue, and reassessment."""

    def __init__(
        self,
        repository: CaseRepository | None = None,
        assessment_engine: DefaultAssessmentEngine | None = None,
        fact_extractor: FactExtractor | None = None,
        planner: ClarificationPlanner | None = None,
        generator: AuditableResponseGenerator | None = None,
        retriever: Any = None,
    ) -> None:
        self.repository = repository or InMemoryCaseRepository()
        self.assessment_engine = assessment_engine or DefaultAssessmentEngine()
        self.fact_extractor = fact_extractor or FactExtractor()
        self.planner = planner or ClarificationPlanner()
        self.generator = generator or AuditableResponseGenerator()
        self.retriever = retriever

    async def create_case(
        self,
        case_id: str,
        complaint_text: str,
        documents: list[DocumentExtractionPayload] | None = None,
        reference_date: date | None = None,
        language: str = "en",
        retrieval_response: RetrievalResponse | None = None,
    ) -> tuple[CaseState, GeneratedResponse, ClarificationPlan]:
        """Initialize a new grievance case from an investor complaint."""
        existing = await self.repository.get_case(case_id)
        if existing:
            raise ValueError(f"Case '{case_id}' already exists.")

        # 1. Fact Extraction
        docs = documents or []
        doc_payload = docs[0] if docs else None
        input_text = complaint_text or ""
        if doc_payload and doc_payload.raw_content:
            input_text = f"{input_text}\n{doc_payload.raw_content}".strip()

        extract_req = FactExtractionRequest(
            input_text=input_text,
            source_id=f"complaint_{case_id}",
            source_type=EvidenceType.DOCUMENT if doc_payload else EvidenceType.USER_STATEMENT,
            reference_date=reference_date,
            language=language,
        )
        extraction_res = self.fact_extractor.extract(extract_req)

        # 2. Case Integration: Proposals -> Confirmed Evidence & Facts
        committed_evidence, committed_facts, warnings = CaseIntegrator.integrate_proposals(
            extraction_result=extraction_res,
            case_id=case_id,
        )

        # 3. Provision Retrieval
        retrieval = retrieval_response or RetrievalResponse(results=[], total_candidates_found=0)

        # 4. Epistemic Assessment
        assess_req = AssessmentRequest(
            case_id=case_id,
            case_facts=committed_facts,
            evidence_items=committed_evidence,
            retrieval_response=retrieval,
            incident_date=committed_facts.get("transaction_date") or reference_date,
            target_organisation=committed_facts.get("organisation"),
        )
        assessment_res = self.assessment_engine.assess(assess_req)

        # 5. Create Initial Case State
        initial_status = self._map_assessment_to_case_status(assessment_res.status)
        case_state = CaseState(
            case_id=case_id,
            version=1,
            status=initial_status,
            facts=committed_facts,
            evidence=committed_evidence,
            hypotheses=["Potentially applicable regulatory tariff or intermediary fee schedule"],
            declined_fields=[],
            clarification_rounds=0,
            retrieval_state=retrieval,
            current_assessment=assessment_res,
            evidence_requirements=assessment_res.evidence_requirements,
        )

        # 6. Snapshot Initial Assessment
        snapshot = AssessmentSnapshot(
            snapshot_id=f"SNAP-{uuid.uuid4().hex[:8].upper()}",
            case_id=case_id,
            case_version=1,
            assessment_result=assessment_res,
            trigger_event_id=None,
        )
        case_state.assessment_history.append(snapshot)

        # 7. Clarification Planning
        plan = self.planner.plan(case_state, assessment_res, language=language)
        self._validate_planned_questions(plan, case_state, assessment_res)
        case_state.unresolved_questions = [q.model_dump() for q in plan.questions]

        # 8. Auditable Generation
        gen_response = self.generator.generate_response(
            assessment=assessment_res,
            retrieval=retrieval,
            evidence_items=committed_evidence,
            case_facts=committed_facts,
            clarification_plan=plan,
        )

        # 9. Record Initial CASE_CREATED Event
        init_event = CaseEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
            case_id=case_id,
            case_version=1,
            event_type=CaseEventType.CASE_CREATED,
            payload={
                "complaint_text": complaint_text,
                "initial_facts": {k: str(v) for k, v in committed_facts.items()},
                "initial_status": initial_status.value,
                "assessment_status": assessment_res.status.value,
            },
            actor="USER",
            source="complaint",
        )
        case_state.interaction_history.append(init_event)

        # 10. Persist State
        saved_case = await self.repository.save_case(case_state)
        return saved_case, gen_response, plan

    async def process_user_turn(
        self,
        case_id: str,
        user_message: str | None = None,
        documents: list[DocumentExtractionPayload] | None = None,
        expected_version: int = 1,
        idempotency_key: str | None = None,
        language: str = "en",
        retrieval_response: RetrievalResponse | None = None,
    ) -> tuple[CaseState, GeneratedResponse, ClarificationPlan, AssessmentDelta]:
        """Process a follow-up user turn with clarification answers or documents."""
        # 1. Idempotency Check
        if idempotency_key:
            existing_event = await self.repository.get_event_by_idempotency_key(case_id, idempotency_key)
            if existing_event:
                logger.info(f"Idempotency hit for key '{idempotency_key}': returning current state.")
                current_state = await self.repository.get_case(case_id)
                if not current_state:
                    raise ValueError(f"Case '{case_id}' missing.")
                retrieval = current_state.retrieval_state or RetrievalResponse(results=[], total_candidates_found=0)
                gen_resp = self.generator.generate_response(
                    assessment=current_state.current_assessment,
                    retrieval=retrieval,
                    evidence_items=current_state.evidence,
                    case_facts=current_state.facts,
                )
                dummy_delta = current_state.latest_delta or AssessmentDelta(
                    case_id=case_id,
                    new_status=current_state.current_assessment.status,
                    rationale="Idempotent duplicate request; no state change.",
                )
                dummy_plan = ClarificationPlan(
                    case_id=case_id,
                    case_version=current_state.version,
                    status=ClarificationPlanStatus.RESOLVED,
                )
                return current_state, gen_resp, dummy_plan, dummy_delta

        # 2. Fetch and Validate Current State
        current_state = await self.repository.get_case(case_id)
        if not current_state:
            raise ValueError(f"Case '{case_id}' does not exist.")

        if current_state.version != expected_version:
            raise CaseVersionConflictError(
                f"CASE_VERSION_CONFLICT: Expected version {expected_version}, but found {current_state.version}.",
                expected_version=expected_version,
                actual_version=current_state.version,
            )

        updated_state = deepcopy(current_state)
        prev_assessment = updated_state.current_assessment

        # 3. Extract Facts from New Input
        raw_text = user_message or ""
        docs = documents or []
        doc_payload = docs[0] if docs else None
        input_text = raw_text
        if doc_payload and doc_payload.raw_content:
            input_text = f"{input_text}\n{doc_payload.raw_content}".strip()

        source_id = doc_payload.document_id if doc_payload else f"turn_{case_id}_{expected_version + 1}"
        extract_req = FactExtractionRequest(
            input_text=input_text,
            source_id=source_id,
            source_type=EvidenceType.DOCUMENT if doc_payload else EvidenceType.USER_STATEMENT,
            reference_date=updated_state.facts.get("transaction_date"),
            language=language,
        )
        extraction_res = self.fact_extractor.extract(extract_req)

        # 4. Integrate Proposals into Evidence
        new_evidence, updated_facts, warnings = CaseIntegrator.integrate_proposals(
            extraction_result=extraction_res,
            case_id=case_id,
            existing_evidence=updated_state.evidence,
            existing_facts=updated_state.facts,
        )

        # Update Evidence in State
        new_evidence_ids = [
            e.evidence_id for e in new_evidence if e not in updated_state.evidence
        ]
        updated_state.evidence = new_evidence
        updated_state.facts = updated_facts

        # 5. Check if User Answer Direct Enum/Value for Unresolved Questions
        self._reconcile_direct_user_answers(user_message, updated_state)

        # 6. Increment Clarification Round
        updated_state.clarification_rounds += 1

        # 7. Incremental / Updated Provision Retrieval
        retrieval = retrieval_response or updated_state.retrieval_state or RetrievalResponse(results=[], total_candidates_found=0)
        updated_state.retrieval_state = retrieval

        # 8. Reassessment Loop
        assess_req = AssessmentRequest(
            case_id=case_id,
            case_facts=updated_state.facts,
            evidence_items=updated_state.evidence,
            retrieval_response=retrieval,
            incident_date=updated_state.facts.get("transaction_date"),
            target_organisation=updated_state.facts.get("organisation"),
        )
        new_assessment = self.assessment_engine.assess(assess_req)
        updated_state.current_assessment = new_assessment
        updated_state.evidence_requirements = new_assessment.evidence_requirements

        # 9. Compute Assessment Delta
        delta = self._compute_assessment_delta(
            case_id=case_id,
            prev_assessment=prev_assessment,
            new_assessment=new_assessment,
            new_evidence_ids=new_evidence_ids,
        )
        updated_state.latest_delta = delta

        # 10. Record Assessment Snapshot
        snap_id = f"SNAP-{uuid.uuid4().hex[:8].upper()}"
        snapshot = AssessmentSnapshot(
            snapshot_id=snap_id,
            case_id=case_id,
            case_version=expected_version + 1,
            assessment_result=new_assessment,
        )
        updated_state.assessment_history.append(snapshot)

        # 11. Clarification Planning for Next Step
        plan = self.planner.plan(updated_state, new_assessment, language=language)
        self._validate_planned_questions(plan, updated_state, new_assessment)
        updated_state.unresolved_questions = [q.model_dump() for q in plan.questions]

        # Update Overall Case Status
        updated_state.status = self._map_assessment_to_case_status(
            assessment_status=new_assessment.status,
            plan_status=plan.status,
        )

        # 12. Auditable Generation
        gen_response = self.generator.generate_response(
            assessment=new_assessment,
            retrieval=retrieval,
            evidence_items=updated_state.evidence,
            case_facts=updated_state.facts,
            clarification_plan=plan,
        )

        # 13. Construct and Append Case Event
        turn_event = CaseEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
            case_id=case_id,
            case_version=expected_version + 1,
            event_type=CaseEventType.DOCUMENT_ATTACHED if docs else CaseEventType.CLARIFICATION_ANSWERED,
            payload={
                "message": raw_text,
                "has_documents": len(docs) > 0,
                "status_transition": f"{prev_assessment.status.value if prev_assessment else 'NONE'} -> {new_assessment.status.value}",
                "resolved_uncertainties": delta.resolved_uncertainties,
            },
            actor="USER",
            source="user_turn",
            idempotency_key=idempotency_key,
        )

        # 14. Atomic Commit
        committed_case = await self.repository.append_event_and_update(
            case_id=case_id,
            expected_version=expected_version,
            event=turn_event,
            updated_state=updated_state,
        )

        return committed_case, gen_response, plan, delta

    async def process_user_decline(
        self,
        case_id: str,
        field_name: str,
        expected_version: int = 1,
        idempotency_key: str | None = None,
        language: str = "en",
    ) -> tuple[CaseState, GeneratedResponse, ClarificationPlan, AssessmentDelta]:
        """Record when a citizen explicitly declines to provide an evidentiary field."""
        current_state = await self.repository.get_case(case_id)
        if not current_state:
            raise ValueError(f"Case '{case_id}' does not exist.")

        if current_state.version != expected_version:
            raise CaseVersionConflictError(
                f"CASE_VERSION_CONFLICT: Expected version {expected_version}, but found {current_state.version}.",
                expected_version=expected_version,
                actual_version=current_state.version,
            )

        updated_state = deepcopy(current_state)
        if field_name not in updated_state.declined_fields:
            updated_state.declined_fields.append(field_name)

        prev_assessment = updated_state.current_assessment
        retrieval = updated_state.retrieval_state or RetrievalResponse(results=[], total_candidates_found=0)

        # Re-assess with known facts
        assess_req = AssessmentRequest(
            case_id=case_id,
            case_facts=updated_state.facts,
            evidence_items=updated_state.evidence,
            retrieval_response=retrieval,
            incident_date=updated_state.facts.get("transaction_date"),
            target_organisation=updated_state.facts.get("organisation"),
        )
        new_assessment = self.assessment_engine.assess(assess_req)
        updated_state.current_assessment = new_assessment

        delta = self._compute_assessment_delta(
            case_id=case_id,
            prev_assessment=prev_assessment,
            new_assessment=new_assessment,
            new_evidence_ids=[],
        )
        delta.rationale = f"User explicitly declined to provide '{field_name}'. Reassessment proceeding without it."
        updated_state.latest_delta = delta

        # Re-plan clarification (declined field will not be re-asked)
        plan = self.planner.plan(updated_state, new_assessment, language=language)
        updated_state.unresolved_questions = [q.model_dump() for q in plan.questions]
        updated_state.status = self._map_assessment_to_case_status(
            assessment_status=new_assessment.status,
            plan_status=plan.status,
        )

        gen_response = self.generator.generate_response(
            assessment=new_assessment,
            retrieval=retrieval,
            evidence_items=updated_state.evidence,
            case_facts=updated_state.facts,
            clarification_plan=plan,
        )

        decline_event = CaseEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
            case_id=case_id,
            case_version=expected_version + 1,
            event_type=CaseEventType.USER_DECLINED_EVIDENCE,
            payload={"declined_field": field_name},
            actor="USER",
            source="user_decline",
            idempotency_key=idempotency_key,
        )

        committed_case = await self.repository.append_event_and_update(
            case_id=case_id,
            expected_version=expected_version,
            event=decline_event,
            updated_state=updated_state,
        )
        return committed_case, gen_response, plan, delta

    def _reconcile_direct_user_answers(self, user_message: str | None, state: CaseState) -> None:
        """Heuristically map direct colloquial answers to open questions."""
        if not user_message:
            return
        msg_lower = user_message.lower().strip()

        # Check for direct transaction_type answers
        if "delivery" in msg_lower and "transaction_type" not in state.facts:
            state.facts["transaction_type"] = "equity_delivery"
            state.evidence.append(
                EvidenceItem(
                    evidence_id=f"EV-ANS-{uuid.uuid4().hex[:6].upper()}",
                    case_id=state.case_id,
                    evidence_type=EvidenceType.USER_STATEMENT,
                    field_name="transaction_type",
                    value="equity_delivery",
                    source="clarification_answer",
                )
            )
        elif "intraday" in msg_lower and "transaction_type" not in state.facts:
            state.facts["transaction_type"] = "intraday"
            state.evidence.append(
                EvidenceItem(
                    evidence_id=f"EV-ANS-{uuid.uuid4().hex[:6].upper()}",
                    case_id=state.case_id,
                    evidence_type=EvidenceType.USER_STATEMENT,
                    field_name="transaction_type",
                    value="intraday",
                    source="clarification_answer",
                )
            )

        # Check for direct BSDA answers
        if "is_bsda" not in state.facts:
            if any(w in msg_lower for w in ["yes bsda", "yes it is bsda", "bsda account", "ha bsda hai"]):
                state.facts["is_bsda"] = True
                state.evidence.append(
                    EvidenceItem(
                        evidence_id=f"EV-ANS-{uuid.uuid4().hex[:6].upper()}",
                        case_id=state.case_id,
                        evidence_type=EvidenceType.USER_STATEMENT,
                        field_name="is_bsda",
                        value=True,
                        source="clarification_answer",
                    )
                )

    def _compute_assessment_delta(
        self,
        case_id: str,
        prev_assessment: AssessmentResult | None,
        new_assessment: AssessmentResult,
        new_evidence_ids: list[str],
    ) -> AssessmentDelta:
        """Deterministically compute difference between two assessments."""
        prev_status = prev_assessment.status if prev_assessment else None
        status_changed = prev_status != new_assessment.status

        # Changed findings
        prev_findings = {f.finding_id: f.statement for f in (prev_assessment.findings if prev_assessment else [])}
        new_findings = {f.finding_id: f.statement for f in new_assessment.findings}
        changed_findings = [
            f"Finding '{fid}': {stmt}"
            for fid, stmt in new_findings.items()
            if fid not in prev_findings or prev_findings[fid] != stmt
        ]

        # Newly applicable provisions
        prev_provs = {p.provision_id for p in (prev_assessment.evaluated_provisions if prev_assessment else []) if p.overall_applicability == "APPLICABLE"}
        new_provs = {p.provision_id for p in new_assessment.evaluated_provisions if p.overall_applicability == "APPLICABLE"}
        newly_applicable = list(new_provs - prev_provs)
        newly_inapplicable = list(prev_provs - new_provs)

        # Resolved uncertainties
        prev_missing = set(prev_assessment.missing_information if prev_assessment else [])
        new_missing = set(new_assessment.missing_information)
        resolved_uncertainties = list(prev_missing - new_missing)
        remaining_uncertainties = list(new_missing)

        rationale = ""
        if status_changed:
            rationale = f"Status transitioned from {prev_status.value if prev_status else 'NONE'} to {new_assessment.status.value}."
            if resolved_uncertainties:
                rationale += f" Resolved missing fields: {', '.join(resolved_uncertainties)}."
        else:
            rationale = f"Status remains {new_assessment.status.value}."

        return AssessmentDelta(
            case_id=case_id,
            previous_status=prev_status,
            new_status=new_assessment.status,
            status_changed=status_changed,
            changed_findings=changed_findings,
            new_evidence_ids=new_evidence_ids,
            newly_applicable_provisions=newly_applicable,
            newly_inapplicable_provisions=newly_inapplicable,
            resolved_uncertainties=resolved_uncertainties,
            remaining_uncertainties=remaining_uncertainties,
            rationale=rationale,
        )

    def _validate_planned_questions(
        self,
        plan: ClarificationPlan,
        case_state: CaseState,
        assessment: AssessmentResult,
    ) -> None:
        """Validate that all questions in the plan are valid and legal."""
        valid_questions: list[ClarificationQuestion] = []
        for q in plan.questions:
            is_valid, errors = QuestionValidator.validate_question(q, case_state, assessment)
            if is_valid:
                valid_questions.append(q)
            else:
                logger.warning(f"Rejecting invalid planned clarification question '{q.question}': {errors}")
        plan.questions = valid_questions

    def _map_assessment_to_case_status(
        self,
        assessment_status: AssessmentStatus,
        plan_status: ClarificationPlanStatus | None = None,
    ) -> CaseStatus:
        """Map AssessmentStatus and ClarificationPlanStatus to CaseStatus."""
        if assessment_status in {
            AssessmentStatus.VIOLATION_CONFIRMED,
            AssessmentStatus.COMPLIANT_WITH_REGULATION,
            AssessmentStatus.ORGANISATION_POLICY_DEVIATION,
        }:
            return CaseStatus.RESOLVED

        if plan_status == ClarificationPlanStatus.QUESTIONS_REQUIRED:
            return CaseStatus.CLARIFICATION_REQUESTED

        if plan_status == ClarificationPlanStatus.MAX_CLARIFICATIONS_REACHED or plan_status == ClarificationPlanStatus.USER_DECLINED:
            return CaseStatus.INSUFFICIENT_EVIDENCE

        if assessment_status == AssessmentStatus.TEMPORALITY_UNRESOLVED:
            return CaseStatus.TEMPORALITY_UNRESOLVED

        if assessment_status == AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED:
            return CaseStatus.REGULATORY_COVERAGE_UNRESOLVED

        if assessment_status == AssessmentStatus.EVIDENCE_INSUFFICIENT:
            return CaseStatus.CLARIFICATION_REQUESTED

        return CaseStatus.OPEN
