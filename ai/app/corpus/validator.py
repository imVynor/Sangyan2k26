"""Deterministic validation for SANGYAN corpus manifests.

Validates:
- corpus_version presence and non-emptiness
- non-empty sources list
- source_id non-emptiness, stability, and uniqueness
- valid SourceClass enumeration
- organisation_id requirements for organisation sources
- URL syntax, HTTP/HTTPS protocol, lack of local paths and credentials
- expected_domain formatting

Errors deterministically identify the exact source entry by index and source_id.
"""

from typing import Any
from urllib.parse import urlparse

from ai.app.corpus.models import CorpusManifest, CorpusSource
from ai.app.knowledge.source_classes import SourceClass

ALLOWED_SOURCE_CLASSES = {sc.value for sc in SourceClass}


class CorpusValidationError(ValueError):
    """Raised when a corpus manifest fails deterministic validation rules."""
    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or [message]


def validate_source_entry(raw_source: Any, index: int) -> list[str]:
    """Validate a single raw source dictionary entry and return collected error strings."""
    errors: list[str] = []
    prefix = f"Source entry [{index}]"

    if not isinstance(raw_source, dict):
        return [f"{prefix}: must be a mapping/dictionary, got {type(raw_source).__name__}."]

    # 1. source_id validation
    source_id = raw_source.get("source_id")
    if source_id is None:
        errors.append(f"{prefix}: missing required field 'source_id'.")
    elif not isinstance(source_id, str) or not source_id.strip():
        errors.append(f"{prefix}: 'source_id' must be a non-empty string.")
    else:
        prefix = f"Source entry [{index}] ('{source_id.strip()}')"

    # 2. source_class validation
    source_class_val = raw_source.get("source_class")
    if source_class_val is None:
        errors.append(f"{prefix}: missing required field 'source_class'.")
    elif source_class_val not in ALLOWED_SOURCE_CLASSES:
        allowed_str = ", ".join(sorted(ALLOWED_SOURCE_CLASSES))
        errors.append(f"{prefix}: invalid 'source_class' '{source_class_val}'. Allowed classes: {allowed_str}.")

    # 3. organisation_id validation for organisation source classes
    if source_class_val in {
        SourceClass.ORGANISATION_POLICY.value,
        SourceClass.ORGANISATION_PROCEDURE.value,
        SourceClass.ORGANISATION_FAQ.value,
    }:
        org_id = raw_source.get("organisation_id")
        if not org_id or not isinstance(org_id, str) or not org_id.strip():
            errors.append(
                f"{prefix}: 'organisation_id' is required for organisation source_class '{source_class_val}'."
            )

    # 4. url validation
    raw_url = raw_source.get("url")
    if raw_url is None:
        errors.append(f"{prefix}: missing required field 'url'.")
    elif not isinstance(raw_url, str) or not raw_url.strip():
        errors.append(f"{prefix}: 'url' must be a non-empty string.")
    else:
        url_str = raw_url.strip()
        # Reject local file paths and non-http schemes
        if url_str.lower().startswith("file:") or ":\\" in url_str or url_str.startswith("/"):
            errors.append(f"{prefix}: URL must not be a local file path: '{url_str}'.")
        else:
            try:
                parsed = urlparse(url_str)
                if parsed.scheme.lower() not in {"http", "https"}:
                    errors.append(f"{prefix}: URL scheme must be 'http' or 'https', got '{parsed.scheme}'.")
                elif not parsed.netloc:
                    errors.append(f"{prefix}: URL has invalid host: '{url_str}'.")
                elif parsed.username or parsed.password:
                    errors.append(f"{prefix}: URL must not contain embedded user credentials.")
            except Exception as e:
                errors.append(f"{prefix}: malformed URL '{url_str}': {e}.")

    # 5. expected_domain validation (optional)
    expected_domain = raw_source.get("expected_domain")
    if expected_domain is not None:
        if not isinstance(expected_domain, str) or not expected_domain.strip():
            errors.append(f"{prefix}: 'expected_domain' if provided must be a non-empty string.")
        elif "/" in expected_domain or ":" in expected_domain:
            errors.append(
                f"{prefix}: 'expected_domain' must be a plain domain (e.g. 'sebi.gov.in'), not a URL or path: '{expected_domain}'."
            )

    return errors


def validate_manifest_dict(raw_data: Any) -> list[str]:
    """Deterministically inspect raw dictionary before model conversion.
    
    Returns all collected error strings. Empty list indicates clean validation.
    """
    errors: list[str] = []

    if not isinstance(raw_data, dict):
        return ["Manifest content must be a YAML mapping/dictionary at the top level."]

    # corpus_version check
    corpus_version = raw_data.get("corpus_version")
    if corpus_version is None:
        errors.append("Manifest missing required field 'corpus_version'.")
    elif not isinstance(corpus_version, str) or not corpus_version.strip():
        errors.append("Field 'corpus_version' must be a non-empty string (e.g. '2026-10-04-v1').")

    # sources check
    sources = raw_data.get("sources")
    if sources is None:
        errors.append("Manifest missing required field 'sources'.")
        return errors

    if not isinstance(sources, list):
        errors.append("Field 'sources' must be a list of source specifications.")
        return errors

    if len(sources) == 0:
        errors.append("Field 'sources' list cannot be empty. Manifest must define at least one source.")
        return errors

    seen_ids: dict[str, int] = {}
    for idx, entry in enumerate(sources):
        entry_errors = validate_source_entry(entry, idx)
        errors.extend(entry_errors)

        if isinstance(entry, dict) and "source_id" in entry:
            sid = entry["source_id"]
            if isinstance(sid, str) and sid.strip():
                clean_id = sid.strip()
                if clean_id in seen_ids:
                    first_idx = seen_ids[clean_id]
                    errors.append(
                        f"Duplicate source_id '{clean_id}' detected at entry [{idx}] (already defined at entry [{first_idx}])."
                    )
                else:
                    seen_ids[clean_id] = idx

    return errors


def validate_manifest(manifest: CorpusManifest) -> None:
    """Validate an already instantiated CorpusManifest."""
    # Manifest validator has already verified Pydantic invariants.
    # This hook provides explicit confirmation and ensures model compliance.
    if not manifest.corpus_version or not manifest.corpus_version.strip():
        raise CorpusValidationError("corpus_version must not be empty.")
    if not manifest.sources:
        raise CorpusValidationError("sources list must not be empty.")
