"""Case State Repository Interfaces and Implementations for SANGYAN.

Epistemic foundation:
- Append-only event persistence.
- Enforces optimistic concurrency via case_version checks (raises CaseVersionConflictError).
- Enforces idempotency via idempotency_key checks.
- Provides InMemoryCaseRepository for tests and PostgresCaseRepository for production.
"""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import logging
from typing import Any, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.app.assessment.contracts import (
    AssessmentFinding,
    AssessmentResult,
    AssessmentStatus,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceRequirement,
    EvidenceType,
)
from ai.app.case.contracts import (
    AssessmentDelta,
    AssessmentSnapshot,
    CaseEvent,
    CaseEventType,
    CaseState,
    CaseStatus,
    CaseVersionConflictError,
)
from ai.app.case.models import (
    CaseAssessmentORM,
    CaseEventORM,
    CaseEvidenceORM,
    CaseORM,
    ClarificationQuestionORM,
)

logger = logging.getLogger("sangyan.case.repository")


class CaseRepository(ABC):
    """Abstract interface for case state storage."""

    @abstractmethod
    async def get_case(self, case_id: str) -> CaseState | None:
        """Retrieve full case state by case_id."""
        pass

    @abstractmethod
    async def save_case(self, case: CaseState) -> CaseState:
        """Create or initialize a new case state."""
        pass

    @abstractmethod
    async def append_event_and_update(
        self,
        case_id: str,
        expected_version: int,
        event: CaseEvent,
        updated_state: CaseState,
    ) -> CaseState:
        """Atomically append event and advance case state version.
        
        Raises CaseVersionConflictError if expected_version != current version.
        """
        pass

    @abstractmethod
    async def get_event_by_idempotency_key(
        self,
        case_id: str,
        idempotency_key: str,
    ) -> CaseEvent | None:
        """Retrieve existing event matching idempotency key if present."""
        pass


class InMemoryCaseRepository(CaseRepository):
    """Deterministic, thread-safe in-memory case repository for fast testing."""

    def __init__(self) -> None:
        self._cases: dict[str, CaseState] = {}
        self._events: dict[str, list[CaseEvent]] = {}
        self._idempotency_index: dict[tuple[str, str], CaseEvent] = {}

    async def get_case(self, case_id: str) -> CaseState | None:
        case = self._cases.get(case_id)
        return deepcopy(case) if case else None

    async def save_case(self, case: CaseState) -> CaseState:
        stored = deepcopy(case)
        self._cases[case.case_id] = stored
        if case.case_id not in self._events:
            self._events[case.case_id] = []
        for ev in stored.interaction_history:
            if ev.idempotency_key:
                self._idempotency_index[(stored.case_id, ev.idempotency_key)] = deepcopy(ev)
        return deepcopy(stored)

    async def get_event_by_idempotency_key(
        self,
        case_id: str,
        idempotency_key: str,
    ) -> CaseEvent | None:
        ev = self._idempotency_index.get((case_id, idempotency_key))
        return deepcopy(ev) if ev else None

    async def append_event_and_update(
        self,
        case_id: str,
        expected_version: int,
        event: CaseEvent,
        updated_state: CaseState,
    ) -> CaseState:
        current = self._cases.get(case_id)
        if not current:
            raise ValueError(f"Case '{case_id}' does not exist.")

        # Idempotency check
        if event.idempotency_key:
            existing = self._idempotency_index.get((case_id, event.idempotency_key))
            if existing:
                logger.info(f"Duplicate event ignored for idempotency key '{event.idempotency_key}'")
                return deepcopy(current)

        # Optimistic concurrency check
        if current.version != expected_version:
            raise CaseVersionConflictError(
                f"CASE_VERSION_CONFLICT: Expected version {expected_version}, but found {current.version}.",
                expected_version=expected_version,
                actual_version=current.version,
            )

        # Apply update
        new_version = expected_version + 1
        event.case_version = new_version
        updated_state.version = new_version
        updated_state.updated_at = datetime.now(timezone.utc)

        # Record event
        self._events[case_id].append(deepcopy(event))
        if event.idempotency_key:
            self._idempotency_index[(case_id, event.idempotency_key)] = deepcopy(event)

        # Record interaction history inside state
        updated_state.interaction_history.append(deepcopy(event))
        self._cases[case_id] = deepcopy(updated_state)
        return deepcopy(updated_state)


class PostgresCaseRepository(CaseRepository):
    """PostgreSQL-backed case repository with atomic transactions and explicit locking."""

    def __init__(self, session_factory: Any) -> None:
        self.session_factory = session_factory

    async def get_case(self, case_id: str) -> CaseState | None:
        async with self.session_factory() as session:
            stmt = select(CaseORM).where(CaseORM.case_id == case_id)
            res = await session.execute(stmt)
            orm = res.scalar_one_or_none()
            if not orm:
                return None
            return self._orm_to_state(orm)

    async def save_case(self, case: CaseState) -> CaseState:
        async with self.session_factory() as session:
            async with session.begin():
                orm = CaseORM(
                    case_id=case.case_id,
                    version=case.version,
                    status=case.status.value,
                    facts=case.facts,
                    hypotheses=case.hypotheses,
                    declined_fields=case.declined_fields,
                    clarification_rounds=case.clarification_rounds,
                    created_at=case.created_at,
                    updated_at=case.updated_at,
                )
                session.add(orm)
            return case

    async def get_event_by_idempotency_key(
        self,
        case_id: str,
        idempotency_key: str,
    ) -> CaseEvent | None:
        async with self.session_factory() as session:
            stmt = select(CaseEventORM).where(
                CaseEventORM.case_id == case_id,
                CaseEventORM.idempotency_key == idempotency_key,
            )
            res = await session.execute(stmt)
            orm = res.scalar_one_or_none()
            if not orm:
                return None
            return CaseEvent(
                event_id=orm.event_id,
                case_id=orm.case_id,
                case_version=orm.case_version,
                event_type=CaseEventType(orm.event_type),
                payload=orm.payload,
                actor=orm.actor,
                source=orm.source,
                idempotency_key=orm.idempotency_key,
                created_at=orm.created_at,
            )

    async def append_event_and_update(
        self,
        case_id: str,
        expected_version: int,
        event: CaseEvent,
        updated_state: CaseState,
    ) -> CaseState:
        async with self.session_factory() as session:
            async with session.begin():
                # Lock row for update
                stmt = select(CaseORM).where(CaseORM.case_id == case_id).with_for_update()
                res = await session.execute(stmt)
                orm = res.scalar_one_or_none()
                if not orm:
                    raise ValueError(f"Case '{case_id}' does not exist.")

                # Idempotency check
                if event.idempotency_key:
                    idemp_stmt = select(CaseEventORM).where(
                        CaseEventORM.case_id == case_id,
                        CaseEventORM.idempotency_key == event.idempotency_key,
                    )
                    idemp_res = await session.execute(idemp_stmt)
                    if idemp_res.scalar_one_or_none():
                        logger.info(f"Duplicate event ignored for idempotency key '{event.idempotency_key}'")
                        return self._orm_to_state(orm)

                # Concurrency check
                if orm.version != expected_version:
                    raise CaseVersionConflictError(
                        f"CASE_VERSION_CONFLICT: Expected version {expected_version}, but found {orm.version}.",
                        expected_version=expected_version,
                        actual_version=orm.version,
                    )

                new_version = expected_version + 1
                orm.version = new_version
                orm.status = updated_state.status.value
                orm.facts = updated_state.facts
                orm.hypotheses = updated_state.hypotheses
                orm.declined_fields = updated_state.declined_fields
                orm.clarification_rounds = updated_state.clarification_rounds
                orm.updated_at = datetime.now(timezone.utc)

                event_orm = CaseEventORM(
                    event_id=event.event_id,
                    case_id=case_id,
                    case_version=new_version,
                    event_type=event.event_type.value,
                    payload=event.payload,
                    actor=event.actor,
                    source=event.source,
                    idempotency_key=event.idempotency_key,
                    created_at=event.created_at,
                )
                session.add(event_orm)

                updated_state.version = new_version
                updated_state.updated_at = orm.updated_at
                return updated_state

    @staticmethod
    def _orm_to_state(orm: CaseORM) -> CaseState:
        return CaseState(
            case_id=orm.case_id,
            version=orm.version,
            status=CaseStatus(orm.status),
            facts=orm.facts or {},
            hypotheses=orm.hypotheses or [],
            declined_fields=orm.declined_fields or [],
            clarification_rounds=orm.clarification_rounds or 0,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
