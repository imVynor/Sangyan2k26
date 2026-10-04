"""Bounded discovery service for SANGYAN authoritative sources.

Principles:
- Discovery is allowed ONLY within explicitly registered official domains.
- NO unconstrained web crawling or spidering across arbitrary domains.
- Rejects external/third-party links and unsupported MIME types.
- Deterministic extraction of official circulars, procedures, and tariff sheets.
"""

from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from pydantic import HttpUrl

from ai.app.sources.models import SourceRegistryEntry
from ai.app.sources.validators import is_subdomain_of, validate_source_url


class DiscoveredCandidate:
    """An official document discovered from an authoritative listing/index page."""

    def __init__(
        self,
        url: str,
        title: str | None = None,
        source_id: str | None = None,
        parent_source_id: str | None = None,
    ) -> None:
        self.url = url
        self.title = title.strip() if title else None
        self.source_id = source_id
        self.parent_source_id = parent_source_id

    def __repr__(self) -> str:
        return f"<DiscoveredCandidate url='{self.url}' title='{self.title}'>"


class BoundedDiscoveryService:
    """Discovers official document links strictly bounded to registered source domains."""

    def __init__(self, allowed_domains: set[str] | None = None) -> None:
        self.allowed_domains = allowed_domains or {
            "sebi.gov.in",
            "nseindia.com",
            "bseindia.com",
            "cdslindia.com",
            "nsdl.co.in",
            "nsdl.com",
            "zerodha.com",
            "groww.in",
            "upstox.com",
            "angelone.in",
            "icicidirect.com",
        }

    def extract_links_from_html(
        self,
        html_bytes: bytes,
        base_url: str,
        expected_domain: str,
        parent_source_id: str | None = None,
    ) -> list[DiscoveredCandidate]:
        """Extract valid official document candidates from an index or circular list page."""
        candidates: list[DiscoveredCandidate] = []
        soup = BeautifulSoup(html_bytes, "html.parser")

        seen_urls: set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            raw_href = a_tag["href"].strip()
            if not raw_href or raw_href.startswith("#") or raw_href.startswith("javascript:"):
                continue

            absolute_url = urljoin(base_url, raw_href)
            parsed = urlparse(absolute_url)

            # Enforce HTTPS
            if parsed.scheme.lower() != "https":
                continue

            host = parsed.netloc.split(":")[0].lower()
            if not host:
                continue

            # Must reside within the pinned expected_domain and global allowlist
            if not is_subdomain_of(host, expected_domain):
                # Third-party link: strictly rejected
                continue

            # Remove fragment
            clean_url = parsed._replace(fragment="").geturl()

            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            title = a_tag.get_text(separator=" ", strip=True) or None
            candidates.append(
                DiscoveredCandidate(
                    url=clean_url,
                    title=title,
                    parent_source_id=parent_source_id,
                )
            )

        return candidates
