"""SANGYAN Reproducible Corpus Manifest System.

Guarantees explicit, auditable, and reproducible knowledge acquisition.
Prohibits autonomous crawling and open web scraping.
"""

from ai.app.corpus.loader import load_manifest, load_manifest_from_string
from ai.app.corpus.models import (
    CorpusManifest,
    CorpusRunResult,
    CorpusSource,
    SourceExecutionStatus,
    SourceRunResult,
)
from ai.app.corpus.validator import CorpusValidationError, validate_manifest


def __getattr__(name: str):
    if name == "CorpusRunner":
        from ai.app.corpus.runner import CorpusRunner
        return CorpusRunner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CorpusManifest",
    "CorpusSource",
    "CorpusRunResult",
    "SourceExecutionStatus",
    "SourceRunResult",
    "CorpusRunner",
    "CorpusValidationError",
    "load_manifest",
    "load_manifest_from_string",
    "validate_manifest",
]
