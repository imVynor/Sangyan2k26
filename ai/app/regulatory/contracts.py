"""Contracts and interfaces for the regulatory knowledge domain.

Defines ingestion request/response envelopes and search query filters.
Deterministic implementations (database, search) belong to future phases.
"""

from abc import ABC, abstractmethod
from datetime import date
from pydantic import BaseModel, Field

from ai.app.knowledge.documents import RegulatoryDocument
from ai.app.knowledge.provisions import RegulatoryProvision


class RegulatoryIngestionRequest(BaseModel):
    """Contract for submitting an official regulatory document for ingestion."""
    document: RegulatoryDocument
    provisions: list[RegulatoryProvision] = Field(default_factory=list)
    raw_content: str | None = Field(default=None, description="Original HTML or text content")


class RegulatoryIngestionResult(BaseModel):
    """Result envelope confirming regulatory ingestion and validation."""
    document_id: str
    success: bool
    provisions_ingested: int
    errors: list[str] = Field(default_factory=list)


class RegulatoryQueryFilter(BaseModel):
    """Criteria for deterministic retrieval of regulatory provisions."""
    authority: str | None = None
    document_identifier: str | None = None
    incident_date: date | None = None
    section: str | None = None
    clause: str | None = None
    keywords: list[str] = Field(default_factory=list)


class RegulatoryKnowledgeRepository(ABC):
    """Abstract contract for future storage and retrieval of regulatory knowledge."""

    @abstractmethod
    async def get_document(self, document_id: str) -> RegulatoryDocument | None:
        """Fetch regulatory document by unique ID."""
        ...

    @abstractmethod
    async def get_provision(self, provision_id: str) -> RegulatoryProvision | None:
        """Fetch individual provision by unique ID."""
        ...

    @abstractmethod
    async def list_provisions_for_document(self, document_id: str) -> list[RegulatoryProvision]:
        """Fetch all provisions belonging to a document."""
        ...
