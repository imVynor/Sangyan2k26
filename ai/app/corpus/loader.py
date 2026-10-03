"""Corpus manifest loader for SANGYAN.

Safely loads, parses, and validates YAML manifest files.
Strictly relies on yaml.safe_load to guarantee that manifest files are treated
purely as configuration data and never evaluated as executable code.
"""

from pathlib import Path
from typing import Any
import yaml

from ai.app.corpus.models import CorpusManifest
from ai.app.corpus.validator import CorpusValidationError, validate_manifest_dict


def load_manifest_from_string(yaml_content: str, source_description: str = "<string>") -> CorpusManifest:
    """Parse and validate YAML manifest string into typed CorpusManifest.
    
    Args:
        yaml_content: Raw YAML text.
        source_description: Descriptive name of source (file path or identifier) for error reports.
    
    Returns:
        Validated CorpusManifest instance.
        
    Raises:
        CorpusValidationError: If YAML is malformed or violates validation invariants.
    """
    if not yaml_content or not yaml_content.strip():
        raise CorpusValidationError(f"Empty manifest content in {source_description}.")

    try:
        raw_data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        raise CorpusValidationError(f"Malformed YAML in {source_description}: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise CorpusValidationError(
            f"Invalid manifest structure in {source_description}: root must be a mapping/dict, got {type(raw_data).__name__}."
        )

    # Deterministic pre-validation across all entries
    errors = validate_manifest_dict(raw_data)
    if errors:
        error_summary = "\n".join(f"  - {err}" for err in errors)
        raise CorpusValidationError(
            f"Corpus manifest validation failed for {source_description} with {len(errors)} error(s):\n{error_summary}",
            errors=errors,
        )

    try:
        manifest = CorpusManifest.model_validate(raw_data)
        return manifest
    except Exception as exc:
        raise CorpusValidationError(f"Model validation error for {source_description}: {exc}") from exc


def load_manifest(path: str | Path) -> CorpusManifest:
    """Load, parse, and validate a corpus manifest from a filesystem path.
    
    Args:
        path: Path to the .yaml or .yml manifest file.
        
    Returns:
        Validated CorpusManifest.
        
    Raises:
        FileNotFoundError: If the manifest file does not exist.
        CorpusValidationError: If the manifest fails schema or security rules.
    """
    manifest_path = Path(path).resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Corpus manifest not found at path: '{manifest_path}'")
    if not manifest_path.is_file():
        raise ValueError(f"Corpus manifest path must be a file, got directory: '{manifest_path}'")

    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()

    return load_manifest_from_string(content, source_description=str(manifest_path))
