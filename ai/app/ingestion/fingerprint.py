"""Deterministic cryptographic fingerprinting and identifier generation.

Epistemic foundation:
- Content identity is based strictly on cryptographic SHA-256 digest of raw bytes.
- Never use timestamps, URLs, or random UUIDs as content fingerprints.
- Document IDs are deterministic functions of source identity and content hash.
"""

import hashlib
from ai.app.knowledge.source_classes import SourceClass


def compute_source_hash(data: bytes) -> str:
    """Compute deterministic SHA-256 hexadecimal digest of raw content bytes.
    
    The same bytes MUST produce the identical hash.
    Different bytes produce different hashes with cryptographic certainty.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"Expected bytes or bytearray, got {type(data).__name__}")
    return hashlib.sha256(data).hexdigest()


def generate_deterministic_document_id(
    source_class: SourceClass,
    source_hash: str,
    authority: str | None = None,
    organisation_id: str | None = None,
) -> str:
    """Generate a stable, deterministic document identifier.
    
    Strategy:
    - Regulatory: 'doc_reg_{authority.lower()}_{hash[:16]}'
    - Organisation: 'doc_org_{org_id.lower()}_{hash[:16]}'
    - Other: 'doc_sec_{hash[:16]}'
    
    Ensures identical content repeatedly ingested yields the identical document_id.
    """
    short_hash = source_hash[:16]
    if source_class.is_regulatory:
        auth_tag = (authority or "gen").strip().lower().replace(" ", "_")
        return f"doc_reg_{auth_tag}_{short_hash}"
    elif source_class.is_organisation:
        org_tag = (organisation_id or "org").strip().lower().replace(" ", "_")
        return f"doc_org_{org_tag}_{short_hash}"
    else:
        return f"doc_sec_{short_hash}"
