"""Orchestrator State Machine and Lifecycle Transition Guards for SANGYAN.

Epistemic foundation:
- Explicit, deterministic state transitions.
- Invalid state transitions (e.g. RESOLVED -> DRAFT) are strictly rejected.
- A resolved case receiving new evidence must explicitly transition through REOPENED.
- Terminal / closure states (CLOSED_INSUFFICIENT vs RESOLVED) remain epistemically distinct.
"""

import logging
from typing import Set

from ai.app.assessment.contracts import AssessmentStatus
from ai.app.case.contracts import CaseStatus
from ai.app.clarification.contracts import ClarificationPlanStatus
from ai.app.orchestration.contracts import InvalidStateTransitionError

logger = logging.getLogger("sangyan.orchestration.state_machine")


class CaseStateMachine:
    """Enforces valid lifecycle transitions for grievance cases."""

    # Explicit transition graph
    VALID_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
        CaseStatus.DRAFT: {
            CaseStatus.DRAFT,
            CaseStatus.EVIDENCE_COLLECTION,
            CaseStatus.UNDER_ASSESSMENT,
            CaseStatus.REQUIRES_CLARIFICATION,
            CaseStatus.RESOLVED,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.OPEN,
            CaseStatus.CLARIFICATION_REQUESTED,
            CaseStatus.INSUFFICIENT_EVIDENCE,
        },
        CaseStatus.OPEN: {
            CaseStatus.OPEN,
            CaseStatus.DRAFT,
            CaseStatus.EVIDENCE_COLLECTION,
            CaseStatus.UNDER_ASSESSMENT,
            CaseStatus.REQUIRES_CLARIFICATION,
            CaseStatus.RESOLVED,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.CLARIFICATION_REQUESTED,
            CaseStatus.INSUFFICIENT_EVIDENCE,
        },
        CaseStatus.EVIDENCE_COLLECTION: {
            CaseStatus.EVIDENCE_COLLECTION,
            CaseStatus.UNDER_ASSESSMENT,
            CaseStatus.REQUIRES_CLARIFICATION,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.RESOLVED,
            CaseStatus.CLARIFICATION_REQUESTED,
            CaseStatus.INSUFFICIENT_EVIDENCE,
        },
        CaseStatus.UNDER_ASSESSMENT: {
            CaseStatus.UNDER_ASSESSMENT,
            CaseStatus.REQUIRES_CLARIFICATION,
            CaseStatus.RESOLVED,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.EVIDENCE_COLLECTION,
            CaseStatus.CLARIFICATION_REQUESTED,
            CaseStatus.INSUFFICIENT_EVIDENCE,
        },
        CaseStatus.EVALUATING: {
            CaseStatus.UNDER_ASSESSMENT,
            CaseStatus.REQUIRES_CLARIFICATION,
            CaseStatus.RESOLVED,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.EVIDENCE_COLLECTION,
            CaseStatus.CLARIFICATION_REQUESTED,
            CaseStatus.INSUFFICIENT_EVIDENCE,
        },
        CaseStatus.REQUIRES_CLARIFICATION: {
            CaseStatus.REQUIRES_CLARIFICATION,
            CaseStatus.EVIDENCE_COLLECTION,
            CaseStatus.UNDER_ASSESSMENT,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.RESOLVED,
            CaseStatus.CLARIFICATION_REQUESTED,
            CaseStatus.INSUFFICIENT_EVIDENCE,
        },
        CaseStatus.CLARIFICATION_REQUESTED: {
            CaseStatus.CLARIFICATION_REQUESTED,
            CaseStatus.REQUIRES_CLARIFICATION,
            CaseStatus.EVIDENCE_COLLECTION,
            CaseStatus.UNDER_ASSESSMENT,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.RESOLVED,
            CaseStatus.INSUFFICIENT_EVIDENCE,
        },
        CaseStatus.RESOLVED: {
            CaseStatus.RESOLVED,
            CaseStatus.CLOSED,
            CaseStatus.REOPENED,
        },
        CaseStatus.CLOSED: {
            CaseStatus.CLOSED,
            CaseStatus.RESOLVED,
            CaseStatus.REOPENED,
        },
        CaseStatus.CLOSED_INSUFFICIENT: {
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.INSUFFICIENT_EVIDENCE,
            CaseStatus.REOPENED,
        },
        CaseStatus.INSUFFICIENT_EVIDENCE: {
            CaseStatus.INSUFFICIENT_EVIDENCE,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.REOPENED,
        },
        CaseStatus.REGULATORY_COVERAGE_UNRESOLVED: {
            CaseStatus.REGULATORY_COVERAGE_UNRESOLVED,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.REOPENED,
        },
        CaseStatus.TEMPORALITY_UNRESOLVED: {
            CaseStatus.TEMPORALITY_UNRESOLVED,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.REOPENED,
        },
        CaseStatus.REOPENED: {
            CaseStatus.REOPENED,
            CaseStatus.UNDER_ASSESSMENT,
            CaseStatus.EVIDENCE_COLLECTION,
            CaseStatus.REQUIRES_CLARIFICATION,
            CaseStatus.RESOLVED,
            CaseStatus.CLOSED_INSUFFICIENT,
            CaseStatus.CLARIFICATION_REQUESTED,
            CaseStatus.INSUFFICIENT_EVIDENCE,
        },
    }

    @classmethod
    def can_transition(cls, from_status: CaseStatus, to_status: CaseStatus) -> bool:
        """Check whether a transition from from_status to to_status is allowed."""
        allowed = cls.VALID_TRANSITIONS.get(from_status, set())
        return to_status in allowed

    @classmethod
    def validate_transition(
        cls,
        from_status: CaseStatus,
        to_status: CaseStatus,
        reason: str = "",
    ) -> None:
        """Validate transition, raising InvalidStateTransitionError on violation."""
        if not cls.can_transition(from_status, to_status):
            msg = (
                f"Transition from '{from_status.value}' to '{to_status.value}' is prohibited. "
                f"A resolved case must be explicitly reopened before receiving new evidence."
                if from_status in {CaseStatus.RESOLVED, CaseStatus.CLOSED}
                else f"Reason: {reason}"
            )
            logger.error(f"State transition rejected: {from_status.value} -> {to_status.value}")
            raise InvalidStateTransitionError(
                from_status=from_status.value,
                to_status=to_status.value,
                reason=msg,
            )

    @classmethod
    def determine_target_status(
        cls,
        assessment_status: AssessmentStatus,
        plan_status: ClarificationPlanStatus | None = None,
        has_open_questions: bool = False,
    ) -> CaseStatus:
        """Deterministically map epistemic assessment and clarification results to CaseStatus."""
        # 1. Definitive assessments resolve the case
        if assessment_status in {
            AssessmentStatus.VIOLATION_CONFIRMED,
            AssessmentStatus.COMPLIANT_WITH_REGULATION,
            AssessmentStatus.ORGANISATION_POLICY_DEVIATION,
        }:
            return CaseStatus.RESOLVED

        # 2. Active clarification requirements
        if plan_status == ClarificationPlanStatus.QUESTIONS_REQUIRED or has_open_questions:
            return CaseStatus.REQUIRES_CLARIFICATION

        # 3. Explicit terminal / exhaustion statuses
        if plan_status == ClarificationPlanStatus.USER_DECLINED:
            return CaseStatus.CLOSED_INSUFFICIENT

        if plan_status == ClarificationPlanStatus.MAX_CLARIFICATIONS_REACHED:
            return CaseStatus.CLOSED_INSUFFICIENT

        if assessment_status == AssessmentStatus.EVIDENCE_INSUFFICIENT:
            return CaseStatus.CLOSED_INSUFFICIENT

        if assessment_status == AssessmentStatus.TEMPORALITY_UNRESOLVED:
            return CaseStatus.CLOSED_INSUFFICIENT

        if assessment_status == AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED:
            return CaseStatus.CLOSED_INSUFFICIENT

        if assessment_status == AssessmentStatus.CONFLICTING_PROVISIONS:
            return CaseStatus.CLOSED_INSUFFICIENT

        # Default fallback
        return CaseStatus.EVIDENCE_COLLECTION
