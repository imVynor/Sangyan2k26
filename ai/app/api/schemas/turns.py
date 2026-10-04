"""Turn Request and Result Schemas for SANGYAN Frontend API.

Epistemic foundation:
- Accepts client inputs (message, documents, declines, expected_version, idempotency_key).
- Returns rich, auditable turn results exposing assessment, causal delta, questions, and claims.
- Never conflates presentation generation failures with epistemic assessment failures.
"""

from typing import Any
from pydantic import BaseModel, Field

from ai.app.api.schemas.cases import (
    ActionIntentView,
    AssessmentDeltaView,
    AssessmentFindingView,
    AssessmentView,
    ClaimView,
    ClarificationQuestionView,
    EvidenceView,
    _map_source_class,
)
from ai.app.evidence_policy.contracts import Claim
from ai.app.orchestration.contracts import CaseTurnResult


class CreateCaseRequest(BaseModel):
    """Initial citizen grievance payload to bootstrap a case."""
    initial_message: str = Field(description="Natural-language complaint or grievance description")
    language: str = Field(default="en", description="ISO language code, e.g. en, hi, hin")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional client context")


class SubmitTurnRequest(BaseModel):
    """Subsequent citizen message or input during multi-turn dialogue."""
    message: str | None = Field(default=None, description="Natural-language response or clarification")
    declined_field: str | None = Field(default=None, description="Field the citizen explicitly refuses or cannot provide")
    expected_version: int | None = Field(default=None, description="Client's known case version for optimistic concurrency")
    idempotency_key: str | None = Field(default=None, description="Client-generated unique turn key")
    language: str = Field(default="en", description="Language code")
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseTurnResultView(BaseModel):
    """Frontend-safe, structured outcome of an orchestrated reasoning turn."""
    case_id: str
    turn_id: str
    previous_version: int
    new_version: int
    previous_status: str
    new_status: str
    status_transition: str
    new_facts: dict[str, Any] = Field(default_factory=dict)
    claims: list[ClaimView] = Field(default_factory=list)
    accepted_evidence: list[EvidenceView] = Field(default_factory=list)
    assessment: AssessmentView
    assessment_delta: AssessmentDeltaView
    clarification_questions: list[ClarificationQuestionView] = Field(default_factory=list)
    action_intents: list[ActionIntentView] = Field(default_factory=list)
    explanation: str | None = Field(default=None, description="Generated explanatory prose")
    generation_status: str = Field(default="COMPLETED", description="'COMPLETED' or 'FAILED'")
    knowledge_snapshot_id: str = "KNOW-2026-V1"
    duration_ms: float = 0.0


class CreateCaseResponse(BaseModel):
    """Response returned upon initial case creation."""
    case_id: str
    version: int
    status: str
    turn_id: str
    response: CaseTurnResultView


def map_turn_result_to_view(result: CaseTurnResult) -> CaseTurnResultView:
    """Transform internal CaseTurnResult into a stable frontend CaseTurnResultView."""
    # 1. Claims
    claims_view: list[ClaimView] = []
    for c in (result.claims or []):
        if isinstance(c, Claim):
            field_name = getattr(c, "field_name", getattr(c, "field", ""))
            src = getattr(c, "source_type", getattr(c, "source_class", "USER"))
            claims_view.append(ClaimView(
                claim_id=c.claim_id,
                field=field_name,
                claimed_value=str(c.claimed_value) if c.claimed_value is not None else None,
                source_class=_map_source_class(src),
                status=c.status.value if hasattr(c.status, "value") else str(c.status),
                evidence_ids=c.evidence_ids,
                superseded_by=getattr(c, "superseded_by", None),
                resolution_rationale=getattr(c, "claim_text", None) or getattr(c, "resolution_rationale", None),
            ))
        elif isinstance(c, dict):
            field_name = c.get("field_name") or c.get("field", "")
            src = c.get("source_type") or c.get("source_class", "USER")
            claims_view.append(ClaimView(
                claim_id=c.get("claim_id", ""),
                field=field_name,
                claimed_value=str(c.get("claimed_value")) if c.get("claimed_value") is not None else None,
                source_class=_map_source_class(src),
                status=c.get("status", "UNRESOLVED"),
                evidence_ids=c.get("evidence_ids", []),
                superseded_by=c.get("superseded_by"),
                resolution_rationale=c.get("resolution_rationale") or c.get("claim_text"),
            ))

    # 2. Evidence
    evidence_view: list[EvidenceView] = []
    for ev in (result.accepted_evidence or []):
        conf = ev.confidence.value if hasattr(getattr(ev, "confidence", None), "value") else str(getattr(ev, "confidence", "HIGH_SUPPORT"))
        evidence_view.append(EvidenceView(
            evidence_id=ev.evidence_id,
            evidence_type=ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type),
            field_name=getattr(ev, "field_name", ""),
            value=str(ev.value) if getattr(ev, "value", None) is not None else None,
            source=getattr(ev, "source", ""),
            confidence=conf,
            description=getattr(ev, "description", "") or getattr(ev, "field_name", ""),
            metadata=getattr(ev, "provenance", {}) or getattr(ev, "metadata", {}),
        ))

    # 3. Assessment
    findings_view: list[AssessmentFindingView] = []
    for f in (result.assessment_result.findings or []):
        findings_view.append(AssessmentFindingView(
            finding_id=f.finding_id,
            normative_source=getattr(f, "normative_source", "REGULATORY"),
            status=f.status.value if hasattr(f.status, "value") else str(f.status),
            support_level=f.confidence.value if hasattr(getattr(f, "confidence", None), "value") else str(getattr(f, "confidence", "HIGH_SUPPORT")),
            statement=getattr(f, "statement", "") or getattr(f, "summary", ""),
            provision_ids=getattr(f, "provision_ids", []) or getattr(f, "applicable_provisions", []),
            evidence_ids=getattr(f, "evidence_ids", []),
        ))

    conf = getattr(result.assessment_result, "confidence", getattr(result.assessment_result, "overall_support_level", "HIGH_SUPPORT"))
    assessment_view = AssessmentView(
        assessment_id=getattr(result.assessment_result, "assessment_id", f"ASM-{result.case_id}"),
        status=result.assessment_result.status.value if hasattr(result.assessment_result.status, "value") else str(result.assessment_result.status),
        summary=getattr(result.assessment_result, "summary", "") or f"Status: {result.assessment_result.status.value}",
        overall_support_level=conf.value if hasattr(conf, "value") else str(conf),
        findings=findings_view,
        evaluated_provisions_count=len(result.assessment_result.evaluated_provisions),
    )

    # 4. Assessment Delta
    d = result.assessment_delta
    delta_view = AssessmentDeltaView(
        previous_status=d.previous_status.value if d.previous_status and hasattr(d.previous_status, "value") else str(d.previous_status) if d.previous_status else None,
        new_status=d.new_status.value if hasattr(d.new_status, "value") else str(d.new_status),
        status_changed=d.status_changed,
        facts_changed=d.facts_changed,
        claims_changed=d.claims_changed,
        evidence_added=d.evidence_added,
        provisions_added=d.provisions_added,
        provisions_removed=d.provisions_removed,
        conditions_re_evaluated=d.conditions_re_evaluated,
        findings_changed=d.findings_changed,
        clarifications_resolved=d.clarifications_resolved,
        clarifications_created=d.clarifications_created,
        cause=d.cause,
        rationale=d.rationale,
    )

    # 5. Clarification Questions
    questions_view: list[ClarificationQuestionView] = []
    if result.clarification_plan and result.clarification_plan.questions:
        for q in result.clarification_plan.questions:
            fn = getattr(q, "field", getattr(q, "field_name", ""))
            txt = getattr(q, "question", getattr(q, "text", ""))
            rsn = getattr(q, "reason", getattr(q, "rationale", ""))
            aet = getattr(q, "acceptable_evidence_types", getattr(q, "suggested_evidence_types", []))
            questions_view.append(ClarificationQuestionView(
                question_id=q.question_id,
                field_name=fn,
                text=txt,
                priority=q.priority.value if hasattr(q.priority, "value") else str(q.priority),
                rationale=rsn,
                suggested_evidence_types=[
                    t.value if hasattr(t, "value") else str(t) for t in aet
                ],
            ))

    # 6. Action Intents
    intents_view: list[ActionIntentView] = []
    for act in (result.action_intents or []):
        intents_view.append(ActionIntentView(
            intent_id=act.intent_id,
            action_type=act.action_type,
            target=act.target.value if hasattr(act.target, "value") else str(act.target),
            priority=act.priority,
            rationale=act.rationale,
            payload=act.payload,
        ))

    # Safe facts
    safe_facts: dict[str, Any] = {}
    for k, v in result.new_facts.items():
        safe_facts[k] = str(v) if hasattr(v, "is_finite") else v

    explanation = getattr(result.generated_response, "summary", getattr(result.generated_response, "prose", None)) if result.generated_response else None
    gen_status = result.generation_snapshot.status if result.generation_snapshot else ("COMPLETED" if explanation else "FAILED")

    return CaseTurnResultView(
        case_id=result.case_id,
        turn_id=result.turn_id,
        previous_version=result.previous_version,
        new_version=result.new_version,
        previous_status=result.previous_status.value if hasattr(result.previous_status, "value") else str(result.previous_status),
        new_status=result.new_status.value if hasattr(result.new_status, "value") else str(result.new_status),
        status_transition=result.status_transition,
        new_facts=safe_facts,
        claims=claims_view,
        accepted_evidence=evidence_view,
        assessment=assessment_view,
        assessment_delta=delta_view,
        clarification_questions=questions_view,
        action_intents=intents_view,
        explanation=explanation,
        generation_status=gen_status,
        knowledge_snapshot_id=result.knowledge_snapshot_id,
        duration_ms=result.duration_ms,
    )
