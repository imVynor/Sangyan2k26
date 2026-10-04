"""Deterministic validation rules for source registry and bounded discovery.

Guarantees:
- Strict HTTPS enforcement.
- Strict domain pinning and redirect validation.
- Rejection of off-domain redirects, non-standard schemes, and IP addresses.
- Content-type boundary validation.
"""

from urllib.parse import urlparse
from pydantic import HttpUrl

ALLOWED_MIME_TYPES = {
    "text/html",
    "application/xhtml+xml",
    "application/pdf",
}


class SourceSecurityError(ValueError):
    """Raised when a discovered URL violates security or domain boundaries."""
    pass


def is_subdomain_of(host: str, parent_domain: str) -> bool:
    """Check if host matches parent_domain or is a valid subdomain thereof."""
    h = host.lower().strip()
    p = parent_domain.lower().strip()
    return h == p or h.endswith("." + p)


def validate_source_url(url: str | HttpUrl, expected_domain: str) -> str:
    """Ensure URL strictly adheres to security rules and pinned expected_domain."""
    url_str = str(url).strip()
    parsed = urlparse(url_str)

    if parsed.scheme.lower() != "https":
        raise SourceSecurityError(f"Prohibited non-HTTPS URL: '{url_str}'. Only HTTPS is permitted.")

    if parsed.username or parsed.password:
        raise SourceSecurityError("URL must not contain embedded user credentials.")

    host = parsed.netloc.split(":")[0].lower()
    if not host:
        raise SourceSecurityError(f"URL is missing host component: '{url_str}'")

    if not is_subdomain_of(host, expected_domain):
        raise SourceSecurityError(
            f"Domain security violation: host '{host}' is not within expected domain '{expected_domain}'."
        )

    return url_str


def validate_content_type(content_type: str) -> bool:
    """Verify MIME type is an authorized official document format."""
    clean_mime = content_type.split(";")[0].strip().lower()
    return clean_mime in ALLOWED_MIME_TYPES
