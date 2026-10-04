"""Contracts and interfaces for the organisation knowledge domain.

Defines ingestion and query envelopes for broker/intermediary policies,
fee schedules, and procedures.
"""

from abc import ABC, abstractmethod
from datetime import date
from pydantic import BaseModel, Field

from ai.app.knowledge.documents import OrganisationDocument
from ai.app.knowledge.provisions import OrganisationProvision


class OrganisationIngestionRequest(BaseModel):
    """Contract for submitting an intermediary policy/fee schedule for ingestion."""
    document: OrganisationDocument
    provisions: list[OrganisationProvision] = Field(default_factory=list)
    raw_content: str | None = Field(default=None)


class OrganisationIngestionResult(BaseModel):
    """Result envelope confirming organisation policy ingestion."""
    document_id: str
    organisation_id: str
    success: bool
    provisions_ingested: int
    errors: list[str] = Field(default_factory=list)


class OrganisationQueryFilter(BaseModel):
    """Criteria for filtering organisation policies and fee terms."""
    organisation_id: str
    applicable_process: str | None = None
    incident_date: date | None = None
    topic: str | None = None


class OrganisationKnowledgeRepository(ABC):
    """Abstract contract for future storage and retrieval of organisation documentation."""

    @abstractmethod
    async def get_document(self, document_id: str) -> OrganisationDocument | None:
        """Fetch organisation document by unique ID."""
        ...

    @abstractmethod
    async def get_provision(self, provision_id: str) -> OrganisationProvision | None:
        """Fetch individual organisation provision."""
        ...

    @abstractmethod
    async def list_documents_for_org(self, organisation_id: str) -> list[OrganisationDocument]:
        """Fetch all documents for a specific organisation."""
        ...
