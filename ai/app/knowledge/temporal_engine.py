"""Temporal Applicability and Version Resolution Engine for SANGYAN.

Evaluates whether a regulatory or organisation document was legally operative
at a specific incident date (HISTORICAL_RULES) or is currently binding (CURRENT_RULES).

Critical safety rules:
- Latest publication date DOES NOT imply current applicability (must check effective date).
- If temporal bounds cannot be proven from official metadata, return TEMPORALITY_UNRESOLVED.
- Superseded documents remain queryable and APPLICABLE for incidents occurring prior to supersession.
"""

from datetime import date
from typing import Sequence

from ai.app.knowledge.documents import OrganisationDocument, RegulatoryDocument
from ai.app.knowledge.relationships import KnowledgeRelationship, RelationshipType
from ai.app.knowledge.temporal import (
    SupersededStatus,
    TemporalResolutionState,
    TemporalScope,
)


class TemporalApplicabilityEngine:
    """Evaluates regulatory document applicability across timeline regimes."""

    @staticmethod
    def evaluate_applicability(
        scope: TemporalScope,
        target_date: date,
        relationships: Sequence[KnowledgeRelationship] | None = None,
    ) -> TemporalResolutionState:
        """Evaluate temporal applicability against an explicit target date (incident or current)."""
        # 1. Effective date check: Future effective rules are NOT yet binding
        if scope.effective_date is not None and target_date < scope.effective_date:
            return TemporalResolutionState.NOT_YET_EFFECTIVE

        # 2. If effective date is unknown, we cannot establish binding force
        if scope.effective_date is None:
            # Having only publication date does not establish legal enforcement date
            return TemporalResolutionState.TEMPORALITY_UNRESOLVED

        # 3. Check explicit termination date
        if scope.termination_date is not None and target_date > scope.termination_date:
            return TemporalResolutionState.EXPIRED_OR_TERMINATED

        # 4. Check explicit supersession status and relationships
        if scope.superseded_status == SupersededStatus.SUPERSEDED:
            # If termination date was recorded and incident was before termination, it was historically APPLICABLE
            if scope.termination_date is not None:
                if target_date <= scope.termination_date:
                    return TemporalResolutionState.APPLICABLE
                return TemporalResolutionState.SUPERSEDED

            # If relationship graph provides explicit supersession date
            if relationships:
                for rel in relationships:
                    if rel.relationship_type in {RelationshipType.SUPERSEDES, RelationshipType.REPLACES}:
                        if rel.effective_date and target_date < rel.effective_date:
                            # Incident happened before superseding document took effect
                            return TemporalResolutionState.APPLICABLE
                        elif rel.effective_date and target_date >= rel.effective_date:
                            return TemporalResolutionState.SUPERSEDED

            # In the absence of an explicit supersession cutoff date, historical applicability is unresolved
            return TemporalResolutionState.SUPERSEDED

        # 5. Effective date has arrived and document has not expired/been superseded
        return TemporalResolutionState.APPLICABLE

    @classmethod
    def resolve_applicable_document(
        cls,
        documents: Sequence[RegulatoryDocument | OrganisationDocument],
        target_date: date,
        relationships: Sequence[KnowledgeRelationship] | None = None,
    ) -> tuple[RegulatoryDocument | OrganisationDocument | None, TemporalResolutionState]:
        """From a pool of document versions, resolve the legally operative version for target_date."""
        applicable_docs: list[RegulatoryDocument | OrganisationDocument] = []
        statuses: list[TemporalResolutionState] = []

        for doc in documents:
            # Construct temporal scope from document
            scope = TemporalScope(
                publication_date=doc.publication_date,
                effective_date=doc.effective_date,
                termination_date=doc.termination_date,
                superseded_status=doc.superseded_status,
            )
            status = cls.evaluate_applicability(scope, target_date, relationships)
            statuses.append(status)
            if status == TemporalResolutionState.APPLICABLE:
                applicable_docs.append(doc)

        if not applicable_docs:
            # Return specific state if all had same non-applicable outcome (e.g. all NOT_YET_EFFECTIVE)
            if statuses and all(s == TemporalResolutionState.NOT_YET_EFFECTIVE for s in statuses):
                return None, TemporalResolutionState.NOT_YET_EFFECTIVE
            if statuses and all(s == TemporalResolutionState.EXPIRED_OR_TERMINATED for s in statuses):
                return None, TemporalResolutionState.EXPIRED_OR_TERMINATED
            if statuses and all(s == TemporalResolutionState.SUPERSEDED for s in statuses):
                return None, TemporalResolutionState.SUPERSEDED
            return None, TemporalResolutionState.TEMPORALITY_UNRESOLVED

        # If multiple versions were legally operative, choose the one with the latest effective date
        applicable_docs.sort(
            key=lambda d: d.effective_date or date.min,
            reverse=True,
        )
        return applicable_docs[0], TemporalResolutionState.APPLICABLE
