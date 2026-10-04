"""Adversarial Evaluation Taxonomy and Controlled Vocabularies for SANGYAN (Phase 7A).

Epistemic foundation:
- Provides strongly typed classifications for grievance categories, difficulty levels,
  adversarial patterns, retrieval relevance, failure classifications, and financial breakdown errors.
- Never conflates superficial plausibility with rigorous correctness.
"""

from enum import Enum


class CaseCategory(str, Enum):
    """Controlled vocabulary of evaluation grievance case categories."""
    BASIC = "basic"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    TEMPORAL = "temporal"
    CROSS_DOCUMENT = "cross_document"
    COMPOUND_FINANCIAL = "compound_financial"
    REGULATORY_GAP = "regulatory_gap"
    MULTILINGUAL = "multilingual"
    ADVERSARIAL = "adversarial"
    MULTI_TURN = "multi_turn"


class DifficultyLevel(str, Enum):
    """Evaluation case difficulty rating (L1 to L6)."""
    L1 = "L1"  # Straightforward: direct facts, single provision, clean resolution
    L2 = "L2"  # Ambiguous: missing or vague details requiring clarification/unknowns
    L3 = "L3"  # Contradictory: user statement vs ledger/document, requires policy precedence
    L4 = "L4"  # Multi-document: requires cross-referencing regulator + depository + broker
    L5 = "L5"  # Temporal / Compound financial: historical regime or multi-component arithmetic
    L6 = "L6"  # Adversarial: prompt injection, misleading evidence, false authority, trap rules


class AdversarialSubtype(str, Enum):
    """Taxonomy of adversarial vulnerability patterns."""
    AMBIGUOUS_LANGUAGE = "AMBIGUOUS_LANGUAGE"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    MISLEADING_EVIDENCE = "MISLEADING_EVIDENCE"
    WRONG_AUTHORITY = "WRONG_AUTHORITY"
    HISTORICAL_TRAP = "HISTORICAL_TRAP"
    NEAR_MATCH_PROVISION = "NEAR_MATCH_PROVISION"
    MISSING_CORPUS_COVERAGE = "MISSING_CORPUS_COVERAGE"
    COMPOUND_FEE_TRAP = "COMPOUND_FEE_TRAP"
    USER_MISCONCEPTION = "USER_MISCONCEPTION"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    UNSUPPORTED_CONCLUSION_TRAP = "UNSUPPORTED_CONCLUSION_TRAP"


class RetrievalRelevance(str, Enum):
    """Epistemic relevance classification for candidate and gold provisions."""
    REQUIRED = "REQUIRED"          # Mandatory for correct assessment
    SUPPORTING = "SUPPORTING"      # Legally relevant background/procedural rule
    IRRELEVANT = "IRRELEVANT"      # Topical but inapplicable
    MISLEADING = "MISLEADING"      # Sounds relevant but establishes wrong legal condition


class RetrievalFailureClass(str, Enum):
    """Exhaustive classification of retrieval misses."""
    CORPUS_GAP = "CORPUS_GAP"                      # Document/rule not present in database
    TEMPORAL_MISS = "TEMPORAL_MISS"                # Retrieved wrong historical version
    AUTHORITY_MISS = "AUTHORITY_MISS"              # Retrieved lower authority when regulator governs
    QUERY_FORMULATION = "QUERY_FORMULATION"        # Search query failed to formulate legal terms
    EMBEDDING_MISS = "EMBEDDING_MISS"              # Dense vector failed semantic match
    LEXICAL_MISS = "LEXICAL_MISS"                  # Full-text search missed statutory keywords
    RERANKING_MISS = "RERANKING_MISS"              # Present in top-50 but pushed out of top-10
    CROSS_DOCUMENT_MISS = "CROSS_DOCUMENT_MISS"    # Retrieved primary doc but missed companion doc
    VERSION_ALIASING = "VERSION_ALIASING"          # Retrieved superseded circular with similar name
    OTHER = "OTHER"


class CompoundErrorType(str, Enum):
    """Fine-grained classification of compound financial errors."""
    BASE_AMOUNT_INCORRECT = "BASE_AMOUNT_INCORRECT"
    TAX_INCORRECT = "TAX_INCORRECT"
    COMPONENT_MISSING = "COMPONENT_MISSING"
    COMPONENT_DUPLICATED = "COMPONENT_DUPLICATED"
    ROUNDING_ERROR = "ROUNDING_ERROR"
    WRONG_APPLICABILITY = "WRONG_APPLICABILITY"


class ClaimRelationshipType(str, Enum):
    """Relationship between multiple claims on the same empirical field."""
    SUPPORTING = "SUPPORTING"
    CONTRADICTORY = "CONTRADICTORY"
    SUPERSEDING = "SUPERSEDING"
    INDEPENDENT = "INDEPENDENT"


class CaseVisibility(str, Enum):
    """Visibility of evaluation cases to guard against prompt overfitting."""
    PUBLIC = "PUBLIC"    # Available for open validation and unit regression
    HIDDEN = "HIDDEN"    # Held-out evaluation suite for unbiased model benchmarking
