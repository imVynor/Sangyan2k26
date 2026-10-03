"""Organisation domain models and official registry entries for SANGYAN."""

from pydantic import BaseModel, Field, field_validator


class OrganisationDiscoveryPage(BaseModel):
    """Registered official discovery starting point for a market intermediary."""
    page_type: str = Field(description="investor_charter, grievance_mechanism, escalation_matrix, charges, etc.")
    url: str = Field(description="Official URL for topic-bounded discovery.")
    description: str | None = None


class OrganisationEntry(BaseModel):
    """Authoritative profile of a registered market intermediary."""
    organisation_id: str = Field(description="Unique canonical identifier (e.g. 'ORG_ZERODHA').")
    canonical_name: str = Field(description="Official legal or brand name (e.g. 'Zerodha Broking Limited').")
    official_domains: list[str] = Field(
        description="Explicit allowed domains. Third-party or lookalike domains are strictly rejected."
    )
    active: bool = Field(default=True)
    supported_topics: list[str] = Field(default_factory=list)
    discovery_pages: list[OrganisationDiscoveryPage] = Field(default_factory=list)

    @field_validator("official_domains")
    @classmethod
    def normalize_domains(cls, v: list[str]) -> list[str]:
        cleaned = [d.strip().lower() for d in v if d.strip()]
        if not cleaned:
            raise ValueError("Organisation must define at least one official domain.")
        return cleaned

    def is_official_domain(self, domain: str) -> bool:
        """Verify whether a given domain or host is an authorized official domain."""
        d = domain.strip().lower()
        for off in self.official_domains:
            if d == off or d.endswith("." + off):
                return True
        return False
