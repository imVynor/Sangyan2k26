"""Case Projection Schemas and Mappers for SANGYAN Frontend API.

Epistemic foundation:
- Exposes stable frontend-safe projections without exposing internal ORM or database details.
- Retains empirical claim identities, evidence attachments, and contradictions.
- Preserves machine-readable causal explanation in assessment deltas.
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from ai.app.api.schemas.common import ClaimSourceClassView, ClaimStatusView
from ai.app.case.contracts import CaseState, CaseStatus
from ai.app.evidence_policy.contracts import Claim, ClaimStatus, EvidenceAuthorityScope, ResolvedFieldClaim


class ClaimView(BaseModel):
    """Frontend-safe empirical claim representation."""
    claim_id: str
    field: str
    claimed_value: Any
    source_class: str
    status: str
    evidence_ids: list[str] = Field(default_factory=list)
    superseded_by: str | None = None
    resolution_rationale: str | None = None


class EvidenceView(BaseModel):
    """Frontend-safe evidence item representation."""
    evidence_id: str
    evidence_type: str
    field_name: str = ""
    value: Any = None
    source: str = ""
    confidence: str = "HIGH_SUPPORT"
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssessmentFindingView(BaseModel):
    """Individual rule assessment finding."""
    finding_id: str
    normative_source: str = "REGULATORY"
    status: str
    support_level: str
    statement: str
    provision_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class AssessmentView(BaseModel):
    """Frontend projection of a deterministic regulatory assessment."""
    assessment_id: str
    status: str
    summary: str = ""
    overall_support_level: str
    findings: list[AssessmentFindingView] = Field(default_factory=list)
    evaluated_provisions_count: int = 0


class AssessmentDeltaView(BaseModel):
    """Machine-readable causal difference between successive assessments."""
    previous_status: str | None = None
    new_status: str
    status_changed: bool = False
    facts_changed: list[str] = Field(default_factory=list)
    claims_changed: list[str] = Field(default_factory=list)
    evidence_added: list[str] = Field(default_factory=list)
    provisions_added: list[str] = Field(default_factory=list)
    provisions_removed: list[str] = Field(default_factory=list)
    conditions_re_evaluated: list[str] = Field(default_factory=list)
    findings_changed: list[str] = Field(default_factory=list)
    clarifications_resolved: list[str] = Field(default_factory=list)
    clarifications_created: list[str] = Field(default_factory=list)
    cause: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class ClarificationQuestionView(BaseModel):
    """Pending evidentiary clarification question."""
    question_id: str
    field_name: str
    text: str
    priority: str
    rationale: str
    suggested_evidence_types: list[str] = Field(default_factory=list)


class ActionIntentView(BaseModel):
    """Structured future action declaration (execution deferred)."""
    intent_id: str
    action_type: str
    target: str
    priority: str
    rationale: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CaseView(BaseModel):
    """Complete frontend-facing case state projection."""
    case_id: str
    version: int
    status: str
    language: str = "en"
    facts: dict[str, Any] = Field(default_factory=dict)
    claims: list[ClaimView] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[EvidenceView] = Field(default_factory=list)
    unresolved_questions: list[ClarificationQuestionView] = Field(default_factory=list)
    evidence_requirements: list[dict[str, Any]] = Field(default_factory=list)
    current_assessment: AssessmentView | None = None
    latest_assessment_delta: AssessmentDeltaView | None = None
    action_intents: list[ActionIntentView] = Field(default_factory=list)
    generation_status: str = "COMPLETED"
    knowledge_snapshot_id: str = "KNOW-2026-V1"
    created_at: datetime
    updated_at: datetime


def _map_source_class(raw_source: str) -> str:
    """Map internal source string to frontend source class enum."""
    raw = raw_source.upper()
    if "USER" in raw or "GRIEVANCE" in raw or "COMPLAINT" in raw:
        return ClaimSourceClassView.USER_ASSERTED.value
    if "DOCUMENT" in raw or "NOTE" in raw or "STATEMENT" in raw or "FILE" in raw or "PDF" in raw:
        return ClaimSourceClassView.DOCUMENT_ASSERTED.value
    if "MODEL" in raw or "EXTRACTED" in raw:
        return ClaimSourceClassView.MODEL_INTERPRETATION.value
    return ClaimSourceClassView.DERIVED.value


def map_case_state_to_view(case_state: CaseState) -> CaseView:
    """Project authoritative internal CaseState into a frontend-safe CaseView."""
    # 1. Map claims
    claims_view: list[ClaimView] = []
    contradictions: list[dict[str, Any]] = []

    for raw_claim in (case_state.claims or []):
        if isinstance(raw_claim, Claim):
            field_name = getattr(raw_claim, "field_name", getattr(raw_claim, "field", ""))
            src = getattr(raw_claim, "source_type", getattr(raw_claim, "source_class", "USER"))
            sc = _map_source_class(src)
            c_view = ClaimView(
                claim_id=raw_claim.claim_id,
                field=field_name,
                claimed_value=str(raw_claim.claimed_value) if raw_claim.claimed_value is not None else None,
                source_class=sc,
                status=raw_claim.status.value if hasattr(raw_claim.status, "value") else str(raw_claim.status),
                evidence_ids=raw_claim.evidence_ids,
                superseded_by=getattr(raw_claim, "superseded_by", None),
                resolution_rationale=getattr(raw_claim, "claim_text", None) or getattr(raw_claim, "resolution_rationale", None),
            )
            claims_view.append(c_view)
            if raw_claim.status == ClaimStatus.CONTRADICTED:
                contradictions.append({
                    "field": field_name,
                    "claim_id": raw_claim.claim_id,
                    "claimed_value": str(raw_claim.claimed_value),
                    "evidence_ids": raw_claim.evidence_ids,
                    "status": "CONTRADICTED",
                })
        elif isinstance(raw_claim, dict):
            field_name = raw_claim.get("field_name") or raw_claim.get("field", "")
            src = raw_claim.get("source_type") or raw_claim.get("source_class", "USER")
            claims_view.append(ClaimView(
                claim_id=raw_claim.get("claim_id", ""),
                field=field_name,
                claimed_value=str(raw_claim.get("claimed_value")) if raw_claim.get("claimed_value") is not None else None,
                source_class=_map_source_class(src),
                status=raw_claim.get("status", "UNRESOLVED"),
                evidence_ids=raw_claim.get("evidence_ids", []),
                superseded_by=raw_claim.get("superseded_by"),
                resolution_rationale=raw_claim.get("resolution_rationale") or raw_claim.get("claim_text"),
            ))

    # 2. Map evidence
    evidence_view: list[EvidenceView] = []
    for ev in case_state.evidence:
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

    # 3. Map assessment
    assessment_view: AssessmentView | None = None
    if case_state.current_assessment:
        cur = case_state.current_assessment
        findings_view: list[AssessmentFindingView] = []
        for f in (cur.findings or []):
            findings_view.append(AssessmentFindingView(
                finding_id=f.finding_id,
                normative_source=getattr(f, "normative_source", "REGULATORY"),
                status=f.status.value if hasattr(f.status, "value") else str(f.status),
                support_level=f.confidence.value if hasattr(getattr(f, "confidence", None), "value") else str(getattr(f, "confidence", "HIGH_SUPPORT")),
                statement=getattr(f, "statement", "") or getattr(f, "summary", ""),
                provision_ids=getattr(f, "provision_ids", []) or getattr(f, "applicable_provisions", []),
                evidence_ids=getattr(f, "evidence_ids", []),
            ))
        conf = getattr(cur, "confidence", getattr(cur, "overall_support_level", "HIGH_SUPPORT"))
        assessment_view = AssessmentView(
            assessment_id=getattr(cur, "assessment_id", f"ASM-{cur.case_id}"),
            status=cur.status.value if hasattr(cur.status, "value") else str(cur.status),
            summary=getattr(cur, "summary", "") or f"Status: {cur.status.value}",
            overall_support_level=conf.value if hasattr(conf, "value") else str(conf),
            findings=findings_view,
            evaluated_provisions_count=len(cur.evaluated_provisions),
        )

    # 4. Map delta
    delta_view: AssessmentDeltaView | None = None
    if case_state.latest_delta:
        d = case_state.latest_delta
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

    # 5. Map unresolved questions
    questions_view: list[ClarificationQuestionView] = []
    for q in (case_state.unresolved_questions or []):
        if isinstance(q, dict):
            fn = q.get("field") or q.get("field_name", "")
            txt = q.get("question") or q.get("text", "")
            rsn = q.get("reason") or q.get("rationale", "")
            aet = q.get("acceptable_evidence_types") or q.get("suggested_evidence_types", [])
            questions_view.append(ClarificationQuestionView(
                question_id=q.get("question_id", ""),
                field_name=fn,
                text=txt,
                priority=str(q.get("priority", "MEDIUM")),
                rationale=rsn,
                suggested_evidence_types=[t.value if hasattr(t, "value") else str(t) for t in aet],
            ))
        elif hasattr(q, "question_id"):
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
                suggested_evidence_types=[t.value if hasattr(t, "value") else str(t) for t in aet],
            ))

    # 6. Map evidence requirements
    requirements_view: list[dict[str, Any]] = []
    for req in (case_state.evidence_requirements or []):
        stat = req.status.value if hasattr(getattr(req, "status", None), "value") else str(getattr(req, "status", "MISSING"))
        requirements_view.append({
            "requirement_id": getattr(req, "requirement_id", f"REQ-{req.field_name}"),
            "field_name": req.field_name,
            "status": stat,
            "description": getattr(req, "description", None),
            "evidence_ids": getattr(req, "evidence_ids", []),
            "priority": req.priority.value if hasattr(getattr(req, "priority", None), "value") else str(getattr(req, "priority", "MEDIUM")),
        })

    # Convert facts (Decimal -> str/float for JSON safety)
    safe_facts: dict[str, Any] = {}
    for k, v in case_state.facts.items():
        safe_facts[k] = str(v) if hasattr(v, "is_finite") else v

    return CaseView(
        case_id=case_state.case_id,
        version=case_state.version,
        status=case_state.status.value if hasattr(case_state.status, "value") else str(case_state.status),
        language="en",
        facts=safe_facts,
        claims=claims_view,
        contradictions=contradictions,
        evidence=evidence_view,
        unresolved_questions=questions_view,
        evidence_requirements=requirements_view,
        current_assessment=assessment_view,
        latest_assessment_delta=delta_view,
        action_intents=[],  # Populated per-turn result
        generation_status="COMPLETED",
        knowledge_snapshot_id=case_state.knowledge_snapshot_id,
        created_at=case_state.created_at,
        updated_at=case_state.updated_at,
    )
