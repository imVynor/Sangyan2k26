"""Dependency Injection and Security Boundary for SANGYAN API.

Epistemic foundation:
- Provides clean abstraction for Principal authentication and Case access authorization.
- Ensures all endpoints resolve the authoritative CaseOrchestrator singleton.
- Prevents bypass of CaseOrchestrator by providing it as the sole mutation dependency.
"""

from dataclasses import dataclass, field
from typing import Annotated, Any
from fastapi import Depends, Header, HTTPException, Request, status

from ai.app.api.errors import CaseNotFoundError, ForbiddenCaseAccessError, UnauthorizedError
from ai.app.orchestration.orchestrator import CaseOrchestrator


@dataclass
class CurrentPrincipal:
    """Security principal representation (User, API Client, or System)."""
    principal_id: str = "anonymous_citizen"
    role: str = "investor"  # "investor", "analyst", "regulator", "admin"
    scopes: set[str] = field(default_factory=lambda: {"read:case", "write:case"})
    allowed_cases: set[str] | None = None  # None indicates wildcard/unrestricted demo access


class CaseAccessPolicy:
    """Evaluates whether a principal is authorized to read or mutate a case."""

    @classmethod
    def can_read_case(cls, principal: CurrentPrincipal, case_id: str) -> bool:
        if principal.role == "admin" or principal.allowed_cases is None:
            return True
        return case_id in principal.allowed_cases

    @classmethod
    def can_mutate_case(cls, principal: CurrentPrincipal, case_id: str) -> bool:
        if principal.role == "admin" or principal.allowed_cases is None:
            return True
        return case_id in principal.allowed_cases


def get_current_principal(
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
) -> CurrentPrincipal:
    """Extract authenticated principal from transport headers (or fallback for local/testing)."""
    p_id = x_user_id or "investor_default"
    role = x_user_role or "investor"
    return CurrentPrincipal(principal_id=p_id, role=role)


async def get_orchestrator(request: Request) -> CaseOrchestrator:
    """Provide the application's authoritative CaseOrchestrator instance."""
    if hasattr(request.app.state, "orchestrator") and request.app.state.orchestrator is not None:
        return request.app.state.orchestrator
    # Fallback instantiation for isolated sub-apps
    orchestrator = CaseOrchestrator()
    request.app.state.orchestrator = orchestrator
    return orchestrator


async def verify_case_access(
    case_id: str,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    orchestrator: Annotated[CaseOrchestrator, Depends(get_orchestrator)],
) -> None:
    """Verify that the case exists and the principal has permission to access it."""
    if not CaseAccessPolicy.can_read_case(principal, case_id):
        raise ForbiddenCaseAccessError(case_id=case_id, principal_id=principal.principal_id)

    case = await orchestrator.repository.get_case(case_id)
    if not case:
        raise CaseNotFoundError(case_id=case_id)
