"""SANGYAN Case State and Multi-Turn Evidentiary Reasoning Package.

Public exports:
- CaseState
- CaseStatus
- CaseEvent
- CaseEventType
- AssessmentSnapshot
- AssessmentDelta
- CaseVersionConflictError
- CaseRepository
- InMemoryCaseRepository
- PostgresCaseRepository
- CaseService
"""

from ai.app.case.contracts import (
    AssessmentDelta,
    AssessmentSnapshot,
    CaseEvent,
    CaseEventType,
    CaseState,
    CaseStatus,
    CaseVersionConflictError,
)
from ai.app.case.repository import (
    CaseRepository,
    InMemoryCaseRepository,
    PostgresCaseRepository,
)


def __getattr__(name: str):
    if name == "CaseService":
        from ai.app.case.service import CaseService
        return CaseService
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "CaseState",
    "CaseStatus",
    "CaseEvent",
    "CaseEventType",
    "AssessmentSnapshot",
    "AssessmentDelta",
    "CaseVersionConflictError",
    "CaseRepository",
    "InMemoryCaseRepository",
    "PostgresCaseRepository",
    "CaseService",
]
