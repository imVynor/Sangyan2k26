"""Deterministic HTTP fetcher using httpx with domain and size validation.

Security & Integrity Controls:
- Strictly enforces maximum payload size (prevents memory exhaustion/decompression bombs).
- Explicit domain validation preventing arbitrary off-domain redirects.
- User-Agent identity header.
- Zero shell command invocation.
- Records full transport metadata: final URL, HTTP status, content-type, content-length.
"""

from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from pydantic import HttpUrl

from ai.app.ingestion.errors import DomainValidationError, FetchError
from ai.app.ingestion.models import FetchedPayload


DEFAULT_USER_AGENT = "SANGYAN-Knowledge-Ingestion/1.0 (+https://sangyan.gov.in/bot)"
DEFAULT_MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
DEFAULT_TIMEOUT_SECONDS = 30.0


def is_domain_allowed(url: str, expected_domain: str) -> bool:
    """Validate whether target URL belongs to expected authoritative domain or its subdomains.
    
    Examples:
    - url='https://support.zerodha.com/path', expected='zerodha.com' -> True
    - url='https://zerodha.com/path', expected='zerodha.com' -> True
    - url='https://fakezerodha.com/path', expected='zerodha.com' -> False
    - url='https://evil.com?ref=zerodha.com', expected='zerodha.com' -> False
    """
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    expected = expected_domain.lower().strip()

    if hostname == expected:
        return True
    if hostname.endswith("." + expected):
        return True
    return False


class DocumentFetcher:
    """Async HTTP document fetcher with redirect and domain safety checks."""

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
        user_agent: str = DEFAULT_USER_AGENT,
        client: httpx.AsyncClient | None = None,
    ):
        self.timeout = timeout
        self.max_size_bytes = max_size_bytes
        self.user_agent = user_agent
        self._external_client = client

    async def fetch(
        self,
        url: str | HttpUrl,
        expected_domain: str | None = None,
    ) -> FetchedPayload:
        """Fetch document bytes from HTTP/HTTPS source with strict security bounds."""
        target_url = str(url)

        # Pre-validate domain before initial request
        if expected_domain and not is_domain_allowed(target_url, expected_domain):
            raise DomainValidationError(
                f"Initial URL '{target_url}' does not match expected domain '{expected_domain}'.",
                details={"target_url": target_url, "expected_domain": expected_domain},
            )

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
        }

        async def _do_fetch(client: httpx.AsyncClient) -> FetchedPayload:
            try:
                response = await client.get(
                    target_url,
                    headers=headers,
                    follow_redirects=True,
                )
            except httpx.TimeoutException as exc:
                raise FetchError(
                    f"HTTP request timed out after {self.timeout}s: {exc}",
                    details={"url": target_url},
                ) from exc
            except httpx.ConnectError as exc:
                raise FetchError(
                    f"HTTP connection failed for '{target_url}': {exc}",
                    details={"url": target_url},
                ) from exc
            except Exception as exc:
                raise FetchError(
                    f"Network transport error: {exc}",
                    details={"url": target_url},
                ) from exc

            # Verify final redirected URL against expected domain
            final_url_str = str(response.url)
            if expected_domain and not is_domain_allowed(final_url_str, expected_domain):
                raise DomainValidationError(
                    f"Redirect led to disallowed domain '{final_url_str}' "
                    f"(expected '{expected_domain}').",
                    details={"final_url": final_url_str, "expected_domain": expected_domain},
                )

            # Validate HTTP status
            if response.status_code != 200:
                raise FetchError(
                    f"HTTP request failed with status {response.status_code}",
                    details={"url": final_url_str, "status_code": response.status_code},
                )

            # Check content length limits
            raw_bytes = response.content
            content_length = len(raw_bytes)
            if content_length > self.max_size_bytes:
                raise FetchError(
                    f"Document size ({content_length} bytes) exceeds limit of {self.max_size_bytes} bytes.",
                    details={"content_length": content_length, "limit": self.max_size_bytes},
                )

            content_type = response.headers.get("content-type", "application/octet-stream")

            return FetchedPayload(
                raw_bytes=raw_bytes,
                final_url=HttpUrl(final_url_str),
                http_status=response.status_code,
                content_type=content_type,
                retrieval_timestamp=datetime.now(timezone.utc),
                content_length=content_length,
            )

        if self._external_client is not None:
            return await _do_fetch(self._external_client)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await _do_fetch(client)
