"""Case Orchestrator and Epistemic Control Plane for SANGYAN.

Epistemic foundation:
- One authoritative turn lifecycle coordinating extraction, evidence policy, retrieval,
  epistemic assessment, clarification planning, and generation.
- Presentation generation is strictly downstream-only.
- All empirical claims and contradictions are preserved.
- Resolved cases receiving new evidence transition through REOPENED.
- State transitions are strictly validated by the state machine.
"""

from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
import logging
import time
from typing import Any, Sequence
import uuid

from ai.app.assessment.contracts import (
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    EvidenceItem,
    EvidenceType,
)
from ai.app.assessment.engine import DefaultAssessmentEngine
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
)
from ai.app.clarification.planner import ClarificationPlanner
from ai.app.clarification.validator import QuestionValidator
from ai.app.evidence_policy.contracts import (
    Claim,
    ClaimStatus,
    ResolvedFieldClaim,
)
from ai.app.evidence_policy.resolver import EvidencePolicyResolver
from ai.app.extraction.case_integrator import CaseIntegrator
from ai.app.extraction.contracts import FactExtractionRequest
from ai.app.extraction.document_extractor import DocumentExtractionPayload
from ai.app.extraction.extractor import FactExtractor
from ai.app.generation.contracts import GeneratedResponse
from ai.app.generation.generator import AuditableResponseGenerator
from ai.app.orchestration.contracts import (
    ActionIntent,
    ActionTarget,
    AssessmentError,
    CaseTurnResult,
    DuplicateEventError,
    ExtractionError,
    GenerationError,
    GenerationSnapshot,
    InvalidStateTransitionError,
    OrchestrationInputEvent,
    RetrievalError,
)
from ai.app.orchestration.dependency_graph import AssessmentDependencyGraph
from ai.app.orchestration.state_machine import CaseStateMachine
from ai.app.retrieval.contracts import RetrievalResponse

logger = logging.getLogger("sangyan.orchestration.orchestrator")


_DEFAULT_RETRIEVER = object()


class CaseOrchestrator:
    """The central authority for executing grievance reasoning turns."""

    def __init__(
        self,
        repository: CaseRepository | None = None,
        assessment_engine: DefaultAssessmentEngine | None = None,
        fact_extractor: FactExtractor | None = None,
        evidence_resolver: EvidencePolicyResolver | None = None,
        planner: ClarificationPlanner | None = None,
        generator: AuditableResponseGenerator | None = None,
        retriever: Any = _DEFAULT_RETRIEVER,
        knowledge_snapshot_id: str = "KNOW-2026-V1",
    ) -> None:
        self.repository = repository or InMemoryCaseRepository()
        self.assessment_engine = assessment_engine or DefaultAssessmentEngine()
        self.fact_extractor = fact_extractor or FactExtractor()
        self.evidence_resolver = evidence_resolver or EvidencePolicyResolver.default()
        self.planner = planner or ClarificationPlanner(max_questions_per_turn=2, max_rounds=3)
        self.generator = generator or AuditableResponseGenerator()
        if retriever is _DEFAULT_RETRIEVER:
            from ai.app.retrieval.retriever import DefaultProvisionRetriever
            self.retriever = DefaultProvisionRetriever.create_default()
        else:
            self.retriever = retriever
        self.knowledge_snapshot_id = knowledge_snapshot_id

    async def process_turn(
        self,
        case_id: str,
        input_event: OrchestrationInputEvent,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> CaseTurnResult:
        """Execute one complete atomic turn of the grievance reasoning lifecycle."""
        start_time = time.perf_counter()
        turn_id = f"TRN-{uuid.uuid4().hex[:8].upper()}"

        logger.info(f"Starting turn '{turn_id}' for case '{case_id}' (actor={input_event.actor})")

        # -------------------------------------------------------------
        # STEP 1: Idempotency Check
        # -------------------------------------------------------------
        if idempotency_key:
            existing_event = await self.repository.get_event_by_idempotency_key(case_id, idempotency_key)
            if existing_event:
                logger.info(f"Idempotency hit for key '{idempotency_key}'. Returning current case state.")
                current_state = await self.repository.get_case(case_id)
                if not current_state:
                    raise ValueError(f"Case '{case_id}' not found.")
                retrieval = current_state.retrieval_state or RetrievalResponse(results=[], total_candidates_found=0)
                gen_resp = None
                try:
                    gen_resp = self.generator.generate_response(
                        assessment=current_state.current_assessment,
                        retrieval=retrieval,
                        evidence_items=current_state.evidence,
                        case_facts=current_state.facts,
                    )
                except Exception as e:
                    logger.warning(f"Idempotency generator replay warning: {e}")

                dummy_delta = current_state.latest_delta or AssessmentDelta(
                    case_id=case_id,
                    new_status=current_state.current_assessment.status if current_state.current_assessment else AssessmentStatus.EVIDENCE_INSUFFICIENT,
                    rationale="Duplicate idempotent turn; state unchanged.",
                )
                dummy_plan = ClarificationPlan(
                    case_id=case_id,
                    case_version=current_state.version,
                    status=ClarificationPlanStatus.RESOLVED,
                )
                duration_ms = (time.perf_counter() - start_time) * 1000
                return CaseTurnResult(
                    case_id=case_id,
                    turn_id=turn_id,
                    previous_version=current_state.version,
                    new_version=current_state.version,
                    previous_status=current_state.status,
                    new_status=current_state.status,
                    status_transition=f"{current_state.status.value} -> {current_state.status.value}",
                    accepted_evidence=current_state.evidence,
                    new_facts=current_state.facts,
                    claims=current_state.claims,
                    retrieval_response=retrieval,
                    assessment_result=current_state.current_assessment,
                    assessment_delta=dummy_delta,
                    clarification_plan=dummy_plan,
                    generated_response=gen_resp,
                    generation_snapshot=GenerationSnapshot(status="COMPLETED"),
                    knowledge_snapshot_id=self.knowledge_snapshot_id,
                    duration_ms=duration_ms,
                )

        # -------------------------------------------------------------
        # STEP 2: Load Case State & Version Check
        # -------------------------------------------------------------
        current_state = await self.repository.get_case(case_id)
        is_first_turn = (current_state is None)

        events_created: list[CaseEvent] = []
        action_intents: list[ActionIntent] = []

        if is_first_turn:
            prev_version = 0
            new_version = 1
            prev_status = CaseStatus.DRAFT
            state = CaseState(
                case_id=case_id,
                version=1,
                status=CaseStatus.DRAFT,
                knowledge_snapshot_id=self.knowledge_snapshot_id,
            )
            # Record Case Created Event
            init_event = CaseEvent(
                event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
                case_id=case_id,
                case_version=1,
                event_type=CaseEventType.CASE_CREATED,
                payload={"initial_input": input_event.complaint_text or input_event.user_message},
                actor=input_event.actor,
                source=input_event.source,
                idempotency_key=idempotency_key,
            )
            events_created.append(init_event)
        else:
            prev_version = current_state.version
            new_version = prev_version + 1
            prev_status = current_state.status

            # Version Conflict Check
            if expected_version is not None and expected_version != prev_version:
                logger.error(
                    f"CASE_VERSION_CONFLICT: Expected {expected_version}, actual {prev_version} for case '{case_id}'"
                )
                raise CaseVersionConflictError(
                    f"CASE_VERSION_CONFLICT: Expected version {expected_version}, but found {prev_version}.",
                    expected_version=expected_version,
                    actual_version=prev_version,
                )

            state = deepcopy(current_state)

            # Reopening Logic: If case was resolved/closed, reopen it
            if prev_status in {
                CaseStatus.RESOLVED,
                CaseStatus.CLOSED,
                CaseStatus.CLOSED_INSUFFICIENT,
                CaseStatus.INSUFFICIENT_EVIDENCE,
            }:
                has_new_content = bool(
                    input_event.user_message or input_event.complaint_text or input_event.documents
                )
                if has_new_content:
                    logger.info(f"Reopening resolved case '{case_id}' upon receipt of new evidence.")
                    CaseStateMachine.validate_transition(prev_status, CaseStatus.REOPENED)
                    state.status = CaseStatus.REOPENED
                    reopen_event = CaseEvent(
                        event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
                        case_id=case_id,
                        case_version=new_version,
                        event_type=CaseEventType.CASE_REOPENED,
                        payload={
                            "previous_status": prev_status.value,
                            "reason": "New user message or document received for resolved case.",
                        },
                        actor=input_event.actor,
                        source=input_event.source,
                    )
                    events_created.append(reopen_event)

        # -------------------------------------------------------------
        # STEP 3: Handle Explicit User Decline
        # -------------------------------------------------------------
        if input_event.declined_field:
            if input_event.declined_field not in state.declined_fields:
                state.declined_fields.append(input_event.declined_field)
            decline_event = CaseEvent(
                event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
                case_id=case_id,
                case_version=new_version,
                event_type=CaseEventType.USER_DECLINED_EVIDENCE,
                payload={"declined_field": input_event.declined_field},
                actor=input_event.actor,
                source=input_event.source,
                idempotency_key=idempotency_key,
            )
            events_created.append(decline_event)

        # -------------------------------------------------------------
        # STEP 4: Fact & Evidence Extraction
        # -------------------------------------------------------------
        raw_text = input_event.complaint_text or input_event.user_message or ""
        docs = input_event.documents or []
        doc_payload = docs[0] if docs else None
        input_text = raw_text
        if doc_payload and doc_payload.raw_content:
            input_text = f"{input_text}\n{doc_payload.raw_content}".strip()

        committed_evidence = list(state.evidence)
        candidate_facts = dict(state.facts)
        warnings: list[str] = []

        ref_date = state.facts.get("transaction_date") or input_event.reference_date

        # 4a. Extract facts from user narrative with USER_STATEMENT source type
        if raw_text:
            try:
                extract_req_user = FactExtractionRequest(
                    input_text=raw_text,
                    source_id=f"turn_{case_id}_{new_version}",
                    source_type=EvidenceType.USER_STATEMENT,
                    reference_date=ref_date,
                    language=input_event.language,
                )
                user_res = self.fact_extractor.extract(extract_req_user)
                committed_evidence, candidate_facts, user_warns = CaseIntegrator.integrate_proposals(
                    extraction_result=user_res,
                    case_id=case_id,
                    existing_evidence=committed_evidence,
                    existing_facts=candidate_facts,
                )
                warnings.extend(user_warns)
            except Exception as exc:
                logger.error(f"User extraction failed for case '{case_id}': {exc}")
                raise ExtractionError(str(exc))

        # 4b. Extract facts from attached document with DOCUMENT source type
        if doc_payload and doc_payload.raw_content:
            try:
                extract_req_doc = FactExtractionRequest(
                    input_text=doc_payload.raw_content,
                    source_id=doc_payload.document_id,
                    source_type=EvidenceType.DOCUMENT,
                    reference_date=ref_date,
                    language=input_event.language,
                )
                doc_res = self.fact_extractor.extract(extract_req_doc)
                committed_evidence, candidate_facts, doc_warns = CaseIntegrator.integrate_proposals(
                    extraction_result=doc_res,
                    case_id=case_id,
                    existing_evidence=committed_evidence,
                    existing_facts=candidate_facts,
                )
                warnings.extend(doc_warns)
            except Exception as exc:
                logger.error(f"Doc extraction failed for case '{case_id}': {exc}")
                raise ExtractionError(str(exc))

        # -------------------------------------------------------------
        # STEP 5: Claim Formation & Evidence Policy Resolution
        # -------------------------------------------------------------
        # Convert evidence items to claims
        new_evidence_items = [e for e in committed_evidence if e not in state.evidence]
        new_claims = self.evidence_resolver.build_claims_from_evidence(new_evidence_items, case_id=case_id)
        all_claims = list(state.claims or []) + new_claims

        # Resolve operative values for each field via registered policies
        resolved_claims: list[ResolvedFieldClaim] = []
        operative_facts = dict(candidate_facts)
        unique_fields = {e.field_name for e in committed_evidence}

        for field in unique_fields:
            resolved = self.evidence_resolver.resolve_field(
                field_name=field,
                evidence_items=committed_evidence,
                existing_claims=all_claims,
            )
            resolved_claims.append(resolved)
            if resolved.operative_value is not None:
                operative_facts[field] = resolved.operative_value
            elif resolved.status == ClaimStatus.CONTRADICTED:
                # Contradiction detected: clear operative value so downstream logic does not use an unverified fact
                operative_facts.pop(field, None)
                # Contradiction detected: emit event
                contra_event = CaseEvent(
                    event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
                    case_id=case_id,
                    case_version=new_version,
                    event_type=CaseEventType.EVIDENCE_CONTRADICTION_DETECTED,
                    payload={
                        "field_name": field,
                        "rationale": resolved.resolution_rationale,
                        "contradicting_claims": resolved.contradicting_claim_ids,
                    },
                    actor="SYSTEM",
                    source="evidence_policy_resolver",
                )
                events_created.append(contra_event)

        # Handle direct colloquial user answers (e.g. "delivery" or "intraday")
        self._reconcile_direct_user_answers(raw_text, operative_facts, committed_evidence, all_claims)

        # Update case state
        old_facts = dict(state.facts)
        state.facts = operative_facts
        state.evidence = committed_evidence
        state.claims = all_claims

        # -------------------------------------------------------------
        # STEP 6: Incremental Provision Retrieval
        # -------------------------------------------------------------
        affected_dimensions = AssessmentDependencyGraph.detect_affected_dimensions(old_facts, operative_facts)
        logger.info(f"Affected dimensions for case '{case_id}': {affected_dimensions}")

        retrieval: RetrievalResponse
        if input_event.metadata.get("retrieval_response"):
            retrieval = input_event.metadata["retrieval_response"]
        elif self.retriever and (affected_dimensions or state.retrieval_state is None):
            try:
                retrieval = await self._retrieve_incrementally(
                    facts=operative_facts,
                    affected_dimensions=affected_dimensions,
                    raw_text=input_text,
                    reference_date=input_event.reference_date,
                )
            except Exception as r_err:
                logger.error(f"Retrieval failed: {r_err}")
                raise RetrievalError(str(r_err))
        else:
            retrieval = state.retrieval_state or RetrievalResponse(results=[], total_candidates_found=0)

        state.retrieval_state = retrieval

        # -------------------------------------------------------------
        # STEP 7: Epistemic Assessment
        # -------------------------------------------------------------
        prev_assessment = state.current_assessment
        try:
            req_reg_cov = input_event.metadata.get("require_regulatory_coverage")
            if req_reg_cov is None:
                req_reg_cov = False if state.facts.get("organisation") else True

            assess_req = AssessmentRequest(
                case_id=case_id,
                case_facts=state.facts,
                evidence_items=state.evidence,
                retrieval_response=retrieval,
                incident_date=state.facts.get("transaction_date") or input_event.reference_date,
                target_organisation=state.facts.get("organisation"),
                require_regulatory_coverage=req_reg_cov,
                operative_claims=resolved_claims,
                claims=all_claims,
            )
            new_assessment = self.assessment_engine.assess(assess_req)
        except Exception as a_err:
            logger.error(f"Assessment engine failed for case '{case_id}': {a_err}")
            raise AssessmentError(str(a_err))

        state.current_assessment = new_assessment
        state.evidence_requirements = new_assessment.evidence_requirements

        # -------------------------------------------------------------
        # STEP 8: Causal Assessment Delta
        # -------------------------------------------------------------
        delta = AssessmentDependencyGraph.build_causal_delta(
            case_id=case_id,
            prev_assessment=prev_assessment,
            new_assessment=new_assessment,
            old_facts=old_facts,
            new_facts=state.facts,
            new_evidence=new_evidence_items,
            new_claims=new_claims,
        )
        state.latest_delta = delta

        # Snapshot assessment
        snap_id = f"SNAP-{uuid.uuid4().hex[:8].upper()}"
        snapshot = AssessmentSnapshot(
            snapshot_id=snap_id,
            case_id=case_id,
            case_version=new_version,
            assessment_result=new_assessment,
        )
        state.assessment_history.append(snapshot)

        # -------------------------------------------------------------
        # STEP 9: Clarification Planning
        # -------------------------------------------------------------
        state.clarification_rounds += 1
        plan = self.planner.plan(state, new_assessment, language=input_event.language)
        self._validate_planned_questions(plan, state, new_assessment)
        state.unresolved_questions = [q.model_dump() for q in plan.questions]

        # -------------------------------------------------------------
        # STEP 10: State Machine Lifecycle Transition
        # -------------------------------------------------------------
        target_status = CaseStateMachine.determine_target_status(
            assessment_status=new_assessment.status,
            plan_status=plan.status,
            has_open_questions=(len(plan.questions) > 0),
        )

        current_machine_status = state.status
        CaseStateMachine.validate_transition(
            from_status=current_machine_status,
            to_status=target_status,
            reason=delta.rationale,
        )
        state.status = target_status

        # -------------------------------------------------------------
        # STEP 11: Action Intents (Action Planning Boundary)
        # -------------------------------------------------------------
        if target_status == CaseStatus.REQUIRES_CLARIFICATION and plan.questions:
            action_intents.append(
                ActionIntent(
                    action_type="REQUEST_DOCUMENT",
                    target=ActionTarget.USER,
                    payload={
                        "questions": [q.model_dump() for q in plan.questions],
                        "suggested_documents": ["contract_note", "ledger_statement"],
                    },
                    priority="HIGH",
                    rationale="Missing critical transaction facts to evaluate regulatory tariff compliance.",
                )
            )
        elif target_status == CaseStatus.RESOLVED and new_assessment.status == AssessmentStatus.VIOLATION_CONFIRMED:
            action_intents.append(
                ActionIntent(
                    action_type="PREPARE_REGULATORY_PETITION",
                    target=ActionTarget.REGULATOR,
                    payload={
                        "violation": new_assessment.status.value,
                        "findings": [f.model_dump() for f in new_assessment.findings],
                    },
                    priority="HIGH",
                    rationale="Statutory violation confirmed against intermediary tariff regulations.",
                )
            )

        # -------------------------------------------------------------
        # STEP 12: Presentation Generation (Downstream Presentation)
        # -------------------------------------------------------------
        gen_response: GeneratedResponse | None = None
        gen_snapshot: GenerationSnapshot
        try:
            gen_response = self.generator.generate_response(
                assessment=new_assessment,
                retrieval=retrieval,
                evidence_items=state.evidence,
                case_facts=state.facts,
                clarification_plan=plan,
            )
            used_llm_polish = await self.generator.polish_summary(
                response=gen_response,
                assessment=new_assessment,
                retrieval=retrieval,
                user_question=input_event.user_message or input_event.complaint_text,
                language=input_event.language,
            )
            gen_snapshot = GenerationSnapshot(
                model_id=(
                    getattr(
                        self.generator.llm_provider,
                        "model_name",
                        type(self.generator.llm_provider).__name__,
                    )
                    if used_llm_polish and self.generator.llm_provider is not None
                    else "deterministic-fallback"
                ),
                model_version="v1.0.0",
                prompt_version="sangyan-explainer-v3",
                status="COMPLETED",
            )
        except Exception as g_err:
            logger.error(f"Downstream generation failed (non-fatal for assessment): {g_err}")
            gen_snapshot = GenerationSnapshot(
                model_id="mock-llm-deterministic",
                model_version="v1.0.0",
                prompt_version="sangyan-explainer-v2",
                status="FAILED",
                error_message=str(g_err),
            )

        # -------------------------------------------------------------
        # STEP 13: Atomic Persistence
        # -------------------------------------------------------------
        state.version = new_version
        state.updated_at = datetime.now(timezone.utc)

        # Main Turn Event
        turn_event = CaseEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
            case_id=case_id,
            case_version=new_version,
            event_type=CaseEventType.DOCUMENT_ATTACHED if docs else CaseEventType.USER_MESSAGE_RECEIVED,
            payload={
                "message": raw_text,
                "has_documents": len(docs) > 0,
                "transition": f"{prev_status.value} -> {target_status.value}",
                "assessment_status": new_assessment.status.value,
                "generation_status": gen_snapshot.status,
            },
            actor=input_event.actor,
            source=input_event.source,
            idempotency_key=idempotency_key,
        )
        events_created.append(turn_event)

        for evt in events_created:
            state.interaction_history.append(evt)

        # Commit state and events
        if is_first_turn:
            saved_case = await self.repository.save_case(state)
        else:
            saved_case = await self.repository.append_event_and_update(
                case_id=case_id,
                expected_version=prev_version,
                event=turn_event,
                updated_state=state,
            )

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Turn '{turn_id}' completed in {duration_ms:.2f}ms: "
            f"{prev_status.value} -> {target_status.value} (Version {new_version})"
        )

        return CaseTurnResult(
            case_id=case_id,
            turn_id=turn_id,
            previous_version=prev_version,
            new_version=new_version,
            previous_status=prev_status,
            new_status=target_status,
            status_transition=f"{prev_status.value} -> {target_status.value}",
            accepted_evidence=state.evidence,
            new_facts=state.facts,
            claims=state.claims,
            resolved_claims=resolved_claims,
            retrieval_response=retrieval,
            assessment_result=new_assessment,
            assessment_delta=delta,
            clarification_plan=plan,
            generated_response=gen_response,
            generation_snapshot=gen_snapshot,
            action_intents=action_intents,
            events_created=events_created,
            knowledge_snapshot_id=self.knowledge_snapshot_id,
            duration_ms=duration_ms,
        )

    def _validate_planned_questions(
        self,
        plan: ClarificationPlan,
        state: CaseState,
        assessment: AssessmentResult,
    ) -> None:
        """Validate every planned question against the case state and assessment result."""
        valid_questions = []
        for q in plan.questions:
            is_valid, errors = QuestionValidator.validate_question(
                question=q,
                case_state=state,
                assessment_result=assessment,
            )
            if is_valid:
                valid_questions.append(q)
            else:
                logger.warning(
                    f"Question for field '{q.field}' rejected: {errors}"
                )
        plan.questions = valid_questions

    def _reconcile_direct_user_answers(
        self,
        user_message: str | None,
        facts: dict[str, Any],
        evidence_list: list[EvidenceItem],
        claims_list: list[Claim],
    ) -> None:
        """Map direct colloquial responses to open clarification questions."""
        if not user_message:
            return
        lower = user_message.lower().strip()

        # Map transaction types only if not already determined
        if "transaction_type" not in facts or not facts["transaction_type"]:
            if any(w in lower for w in ["delivery", "cnc", "holding", "invested", "shares transferred"]):
                ttype = "equity_delivery"
                if any(w in lower for w in ["sold", "sell", "selling", "sale", "becha"]):
                    ttype = "equity_delivery_sell"
                elif any(w in lower for w in ["bought", "buy", "buying", "purchase"]):
                    ttype = "equity_delivery_buy"
                facts["transaction_type"] = ttype
                ev = EvidenceItem(
                    evidence_id=f"EVID-USER-TXTYPE-{uuid.uuid4().hex[:6]}",
                    case_id="",
                    evidence_type=EvidenceType.USER_STATEMENT,
                    field_name="transaction_type",
                    value=ttype,
                    source="user_dialogue",
                )
                evidence_list.append(ev)
                claims_list.append(
                    Claim(
                        field_name="transaction_type",
                        claim_text=user_message,
                        claimed_value=ttype,
                        source_type=EvidenceType.USER_STATEMENT,
                        evidence_ids=[ev.evidence_id],
                        status=ClaimStatus.RESOLVED_BY_POLICY,
                    )
                )
            elif any(w in lower for w in ["intraday", "mis", "day trading", "squared off"]):
                facts["transaction_type"] = "intraday"
                ev = EvidenceItem(
                    evidence_id=f"EVID-USER-TXTYPE-{uuid.uuid4().hex[:6]}",
                    case_id="",
                    evidence_type=EvidenceType.USER_STATEMENT,
                    field_name="transaction_type",
                    value="intraday",
                    source="user_dialogue",
                )
                evidence_list.append(ev)
                claims_list.append(
                    Claim(
                        field_name="transaction_type",
                        claim_text=user_message,
                        claimed_value="intraday",
                        source_type=EvidenceType.USER_STATEMENT,
                        evidence_ids=[ev.evidence_id],
                        status=ClaimStatus.RESOLVED_BY_POLICY,
                    )
                )

        # Map account type only if not already determined
        if "account_type" not in facts or not facts["account_type"]:
            if "bsda" in lower or "basic service" in lower:
                facts["is_bsda"] = True
                facts["account_type"] = "bsda"
                ev = EvidenceItem(
                    evidence_id=f"EVID-USER-BSDA-{uuid.uuid4().hex[:6]}",
                    case_id="",
                    evidence_type=EvidenceType.USER_STATEMENT,
                    field_name="account_type",
                    value="bsda",
                    source="user_dialogue",
                )
                evidence_list.append(ev)
                claims_list.append(
                    Claim(
                        field_name="account_type",
                        claim_text=user_message,
                        claimed_value="bsda",
                        source_type=EvidenceType.USER_STATEMENT,
                        evidence_ids=[ev.evidence_id],
                        status=ClaimStatus.RESOLVED_BY_POLICY,
                    )
                )

    async def _retrieve_incrementally(
        self,
        facts: dict[str, Any],
        affected_dimensions: set[str],
        raw_text: str = "",
        reference_date: Any = None,
    ) -> RetrievalResponse:
        """Execute incremental provision retrieval using CaseSemanticNormalizer and RetrievalQueryPlanner."""
        if hasattr(self.retriever, "retrieve"):
            import inspect
            from ai.app.retrieval.contracts import RetrievalFailureReason, RetrievalResponse, RetrievalResult
            from ai.app.understanding.contracts import PlannedQuery, QueryType
            from ai.app.understanding.normalizer import CaseSemanticNormalizer
            from ai.app.understanding.query_planner import RetrievalQueryPlanner

            # 1. Semantic normalization from raw input text and existing operative facts
            normalizer = CaseSemanticNormalizer()
            sem = normalizer.normalize(
                raw_text=raw_text,
                existing_facts=facts,
                reference_date=reference_date,
            )

            # 2. Plan structured complementary retrieval queries
            planned_queries = RetrievalQueryPlanner.plan_queries(sem)

            # Fallback if no query planned
            if not planned_queries:
                planned_queries = [
                    PlannedQuery(
                        query_id="FALLBACK-01",
                        query_text=raw_text.strip() or "DP charge tariff regulatory ceiling",
                        query_type=QueryType.PRIMARY_ISSUE,
                        weight=1.0,
                    )
                ]

            # 3. Multi-query execution and deterministic result merging
            all_provisions: dict[str, RetrievalResult] = {}
            total_candidates = 0
            all_authorities: set[str] = set()
            all_organisations: set[str] = set()
            query_breakdown: list[dict[str, Any]] = []

            for pq in planned_queries:
                r_query = RetrievalQueryPlanner.to_retrieval_query(pq)
                res = self.retriever.retrieve(r_query)
                if inspect.isawaitable(res):
                    sub_response = await res
                else:
                    sub_response = res

                total_candidates += sub_response.total_candidates_found
                all_authorities.update(sub_response.routed_authorities)
                all_organisations.update(sub_response.routed_organisations)

                retrieved_pids = []
                for item in sub_response.results:
                    # Enforce organisation isolation: exclude provisions owned by another broker
                    if sem.organisation_id and item.organisation_id and item.organisation_id != sem.organisation_id:
                        continue

                    retrieved_pids.append(item.provision_id)
                    effective_score = round(item.relevance_score * pq.weight, 4)

                    query_tag = f"query:{pq.query_id}"
                    type_tag = f"type:{pq.query_type.value}"

                    if item.provision_id not in all_provisions:
                        item_copy = item.model_copy(deep=True)
                        item_copy.relevance_score = effective_score
                        if query_tag not in item_copy.retrieval_methods:
                            item_copy.retrieval_methods.append(query_tag)
                        if type_tag not in item_copy.retrieval_methods:
                            item_copy.retrieval_methods.append(type_tag)
                        all_provisions[item.provision_id] = item_copy
                    else:
                        existing = all_provisions[item.provision_id]
                        if effective_score > existing.relevance_score:
                            existing.relevance_score = effective_score
                        if query_tag not in existing.retrieval_methods:
                            existing.retrieval_methods.append(query_tag)
                        if type_tag not in existing.retrieval_methods:
                            existing.retrieval_methods.append(type_tag)

                query_breakdown.append({
                    "query_id": pq.query_id,
                    "query_type": pq.query_type.value,
                    "query_text": pq.query_text,
                    "provisions_retrieved": len(retrieved_pids),
                    "target_organisation": pq.target_organisation,
                    "retrieved_provision_ids": retrieved_pids,
                })

            sorted_results = sorted(all_provisions.values(), key=lambda r: r.relevance_score, reverse=True)
            for idx, r in enumerate(sorted_results, 1):
                r.rank = idx

            failure_reasons = []
            if not sorted_results:
                failure_reasons.append(RetrievalFailureReason.NO_RELEVANT_PROVISIONS)

            return RetrievalResponse(
                results=sorted_results[:20],
                total_candidates_found=total_candidates,
                failure_reasons=failure_reasons,
                routed_authorities=sorted(all_authorities),
                routed_organisations=sorted(all_organisations),
                retrieval_stats={
                    "retriever_class": self.retriever.__class__.__name__,
                    "total_merged": len(all_provisions),
                    "queries_executed": len(planned_queries),
                    "query_breakdown": query_breakdown,
                    "semantic_representation": sem.model_dump(),
                },
            )
        return RetrievalResponse(results=[], total_candidates_found=0)
