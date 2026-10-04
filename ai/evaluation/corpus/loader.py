"""Corpus Loader and Directory Indexer for SANGYAN Evaluation Cases (Phase 7A).

Epistemic foundation:
- Discovers and loads evaluation cases from ai/evaluation/cases/ subdirectories.
- Enforces strict public / hidden evaluation suite isolation (Section 27).
- Supports filtering by suite, category, difficulty, visibility, and case_id.
"""

import importlib
import logging
from pathlib import Path
from typing import Sequence

from ai.evaluation.corpus.models import EvaluationCase
from ai.evaluation.corpus.taxonomy import CaseCategory, CaseVisibility, DifficultyLevel

logger = logging.getLogger("sangyan.evaluation.loader")

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"

SUITE_MAPPINGS: dict[str, list[CaseCategory]] = {
    "all": list(CaseCategory),
    "retrieval": [CaseCategory.BASIC, CaseCategory.TEMPORAL, CaseCategory.CROSS_DOCUMENT, CaseCategory.REGULATORY_GAP],
    "assessment": [CaseCategory.BASIC, CaseCategory.CONTRADICTORY, CaseCategory.COMPOUND_FINANCIAL, CaseCategory.AMBIGUOUS],
    "adversarial": [CaseCategory.ADVERSARIAL],
    "multilingual": [CaseCategory.MULTILINGUAL],
    "temporal": [CaseCategory.TEMPORAL],
    "cross-document": [CaseCategory.CROSS_DOCUMENT],
    "compound": [CaseCategory.COMPOUND_FINANCIAL],
    "multi-turn": [CaseCategory.MULTI_TURN],
}


class CorpusLoader:
    """Loads and filters evaluation cases from the corpus directory tree."""

    def __init__(self, root_cases_dir: Path | None = None) -> None:
        self.cases_dir = root_cases_dir or CASES_DIR
        self._cached_cases: list[EvaluationCase] | None = None

    def load_all_cases(self, reload: bool = False) -> list[EvaluationCase]:
        """Load all evaluation cases from all subdirectories."""
        if self._cached_cases is not None and not reload:
            return self._cached_cases

        loaded_cases: list[EvaluationCase] = []

        subdirs = [
            "basic",
            "ambiguous",
            "contradictory",
            "temporal",
            "cross_document",
            "compound_financial",
            "regulatory_gap",
            "multilingual",
            "adversarial",
            "multi_turn",
        ]

        for subdir in subdirs:
            pkg_path = self.cases_dir / subdir
            if not pkg_path.exists():
                continue

            cases_file = pkg_path / "cases.py"
            if cases_file.exists():
                module_name = f"ai.evaluation.cases.{subdir}.cases"
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, "CASES"):
                        for item in getattr(module, "CASES"):
                            if isinstance(item, EvaluationCase):
                                loaded_cases.append(item)
                            elif isinstance(item, dict):
                                loaded_cases.append(EvaluationCase(**item))
                except Exception as e:
                    logger.error(f"Failed to load cases from {module_name}: {e}", exc_info=True)

        self._cached_cases = loaded_cases
        return loaded_cases

    def get_case(self, case_id: str) -> EvaluationCase | None:
        """Find a specific case by its case_id."""
        for case in self.load_all_cases():
            if case.case_id.upper() == case_id.upper():
                return case
        return None

    def filter_cases(
        self,
        suite: str | None = None,
        category: str | CaseCategory | None = None,
        difficulty: str | DifficultyLevel | None = None,
        visibility: CaseVisibility | str = CaseVisibility.PUBLIC,
        case_id: str | None = None,
    ) -> list[EvaluationCase]:
        """Filter loaded cases based on specified criteria."""
        cases = self.load_all_cases()

        if case_id:
            return [c for c in cases if c.case_id.upper() == case_id.upper()]

        # Filter by visibility (Section 27)
        if visibility != "ALL":
            target_vis = CaseVisibility(visibility) if isinstance(visibility, str) else visibility
            cases = [c for c in cases if c.visibility == target_vis]

        # Filter by suite name
        if suite and suite.lower() in SUITE_MAPPINGS:
            allowed_cats = SUITE_MAPPINGS[suite.lower()]
            cases = [
                c for c in cases
                if c.category in allowed_cats
                or any(sc in allowed_cats for sc in c.secondary_categories)
            ]

        # Filter by category
        if category:
            cat_enum = CaseCategory(category.lower()) if isinstance(category, str) else category
            cases = [
                c for c in cases
                if c.category == cat_enum or cat_enum in c.secondary_categories
            ]

        # Filter by difficulty
        if difficulty:
            diff_enum = DifficultyLevel(difficulty.upper()) if isinstance(difficulty, str) else difficulty
            cases = [c for c in cases if c.difficulty == diff_enum]

        return cases
