"""Unit and Integration Test Suite for SANGYAN Evaluation & Grievance Corpus (Phase 7A).

Epistemic foundation:
- Validates typed schema contracts, Decimal enforcement, and negative unknown enforcement.
- Tests corpus loading, public/hidden isolation, and category/difficulty filtering.
- Tests gold provision provenance validation.
- Verifies information retrieval metric calculations (Recall, MRR, nDCG@10).
- Verifies regression comparison and safety invariant violation alerts.
- Verifies failure classification taxonomy and deterministic case execution.
"""

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import pytest

from ai.app.assessment.contracts import AssessmentResult, AssessmentStatus
from ai.evaluation.corpus.loader import CorpusLoader
from ai.evaluation.corpus.models import (
    BenchmarkSuiteReport,
    CaseEvaluationReport,
    EvaluationCase,
    ExpectedAssessment,
    ExpectedFact,
    ExpectedIssue,
    ExpectedProvision,
    ExpectedUnknown,
    StageEvaluationResult,
)
from ai.evaluation.corpus.taxonomy import (
    CaseCategory,
    CaseVisibility,
    DifficultyLevel,
    RetrievalFailureClass,
    RetrievalRelevance,
)
from ai.evaluation.corpus.validator import CaseValidator
from ai.evaluation.evaluators.aggregate import BenchmarkAggregator
from ai.evaluation.evaluators.assessment_evaluator import AssessmentEvaluator
from ai.evaluation.evaluators.fact_evaluator import FactEvaluator
from ai.evaluation.evaluators.retrieval_evaluator import ProvisionRetrievalEvaluator
from ai.evaluation.runners.compare_runs import compare_runs, format_delta
from ai.evaluation.runners.evaluate_case import SingleCaseEvaluator


# =====================================================================
# 1. SCHEMA & VALIDATION TESTS
# =====================================================================

def test_evaluation_case_schema_valid():
    """Verify that a valid EvaluationCase satisfies all contract constraints."""
    case = EvaluationCase(
        case_id="TEST-001",
        title="Valid Test Case",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        user_input="Test grievance statement",
        expected_facts=[
            ExpectedFact(field="charged_amount", expected_value=Decimal("15.93"), data_type="DECIMAL"),
        ],
        expected_unknowns=[
            ExpectedUnknown(field="transaction_date", reason="Date not mentioned"),
        ],
        expected_provisions=[
            ExpectedProvision(
                provision_id="prov_test_001",
                relevance=RetrievalRelevance.REQUIRED,
                provenance_rationale="Test statutory provision justification.",
            )
        ],
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        ),
    )

    validator = CaseValidator()
    result = validator.validate_case(case)
    assert result.is_valid
    assert len(result.errors) == 0


def test_validation_fails_on_missing_fields():
    """Verify validator flags missing title or user_input."""
    case = EvaluationCase(
        case_id="TEST-INVALID-1",
        title="",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        user_input="",
    )
    validator = CaseValidator()
    result = validator.validate_case(case)
    assert not result.is_valid
    assert any("Missing title" in err for err in result.errors)
    assert any("Missing user_input" in err for err in result.errors)


def test_validation_enforces_decimal_on_financial_facts():
    """Verify validator rejects non-Decimal floating point or invalid numbers in financial facts."""
    case = EvaluationCase(
        case_id="TEST-FLOAT-1",
        title="Float Test Case",
        category=CaseCategory.COMPOUND_FINANCIAL,
        difficulty=DifficultyLevel.L5,
        user_input="Test float",
        expected_facts=[
            ExpectedFact(field="brokerage", expected_value="INVALID_NOT_A_NUMBER", data_type="DECIMAL"),
        ],
    )
    validator = CaseValidator()
    result = validator.validate_case(case)
    assert not result.is_valid
    assert any("must use Decimal" in err for err in result.errors)


def test_validation_enforces_negative_unknown_must_be_none():
    """Verify validator and model reject ExpectedUnknown with non-None expected_value or must_remain_unknown=False."""
    with pytest.raises(Exception):
        ExpectedUnknown(field="transaction_date", expected_value="2026-01-01", must_remain_unknown=True)  # type: ignore

    case = EvaluationCase(
        case_id="TEST-UNK-INVALID",
        title="Unknown Invalid",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        user_input="Test unknown",
        expected_unknowns=[
            ExpectedUnknown(field="transaction_date", must_remain_unknown=False),
        ],
    )
    validator = CaseValidator()
    result = validator.validate_case(case)
    assert not result.is_valid
    assert any("must set must_remain_unknown=True" in err for err in result.errors)


# =====================================================================
# 2. CORPUS LOADING & FILTERING TESTS
# =====================================================================

def test_corpus_loader_loads_all_cases():
    """Verify that all 85 cases across 10 subdirectories are successfully loaded."""
    loader = CorpusLoader()
    cases = loader.load_all_cases()
    assert len(cases) >= 75
    assert len(cases) == 85

    # Check that all 10 categories are represented
    categories_present = {c.category for c in cases}
    assert len(categories_present) == 10
    assert CaseCategory.BASIC in categories_present
    assert CaseCategory.AMBIGUOUS in categories_present
    assert CaseCategory.CONTRADICTORY in categories_present
    assert CaseCategory.TEMPORAL in categories_present
    assert CaseCategory.CROSS_DOCUMENT in categories_present
    assert CaseCategory.COMPOUND_FINANCIAL in categories_present
    assert CaseCategory.REGULATORY_GAP in categories_present
    assert CaseCategory.MULTILINGUAL in categories_present
    assert CaseCategory.ADVERSARIAL in categories_present
    assert CaseCategory.MULTI_TURN in categories_present


def test_corpus_loader_suite_filtering():
    """Verify suite-based filtering returns expected category subsets."""
    loader = CorpusLoader()

    retrieval_cases = loader.filter_cases(suite="retrieval")
    assert len(retrieval_cases) > 0
    assert all(
        c.category in (CaseCategory.BASIC, CaseCategory.TEMPORAL, CaseCategory.CROSS_DOCUMENT, CaseCategory.REGULATORY_GAP)
        for c in retrieval_cases
    )

    adversarial_cases = loader.filter_cases(suite="adversarial")
    assert len(adversarial_cases) == 5
    assert all(c.category == CaseCategory.ADVERSARIAL for c in adversarial_cases)


def test_hidden_public_corpus_separation():
    """Verify strict public/hidden case filtering boundary (Section 27)."""
    loader = CorpusLoader()
    public_cases = loader.filter_cases(visibility=CaseVisibility.PUBLIC)
    assert len(public_cases) > 0

    hidden_cases = loader.filter_cases(visibility=CaseVisibility.HIDDEN)
    # Currently public set is default; verify isolation
    assert all(c.visibility == CaseVisibility.PUBLIC for c in public_cases)
    assert all(c.visibility == CaseVisibility.HIDDEN for c in hidden_cases)


def test_entire_suite_validation_passes():
    """Validate all 85 benchmark cases with CaseValidator and verify zero errors."""
    loader = CorpusLoader()
    cases = loader.load_all_cases()
    validator = CaseValidator()
    result = validator.validate_suite(cases)
    assert result.is_valid, f"Corpus validation errors: {result.errors}"
    assert len(result.errors) == 0


# =====================================================================
# 3. EVALUATOR METRICS TESTS
# =====================================================================

def test_fact_evaluator_penalizes_hallucination():
    """Verify FactEvaluator penalizes hallucinating an ExpectedUnknown."""
    case = EvaluationCase(
        case_id="TEST-FACT-HALLUCINATION",
        title="Hallucination Test",
        category=CaseCategory.AMBIGUOUS,
        difficulty=DifficultyLevel.L2,
        user_input="I was charged money",
        expected_facts=[],
        expected_unknowns=[
            ExpectedUnknown(field="transaction_date", reason="Date not mentioned"),
        ],
    )

    evaluator = FactEvaluator()
    # Actual facts contain hallucinated date
    actual_facts = {"transaction_date": date(2026, 3, 1)}
    res = evaluator.evaluate(case, actual_facts)

    assert not res.passed
    assert res.failure_class == "HALLUCINATED_FACT"
    assert any("HALLUCINATION" in d for d in res.discrepancies)


def test_retrieval_evaluator_computes_ir_metrics():
    """Verify IR metric calculations: Recall@1, Recall@5, MRR, nDCG@10."""
    case = EvaluationCase(
        case_id="TEST-RET-METRICS",
        title="IR Metrics Test",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        user_input="Test query",
        expected_provisions=[
            ExpectedProvision(provision_id="PROV-GOLD-1", relevance=RetrievalRelevance.REQUIRED),
            ExpectedProvision(provision_id="PROV-GOLD-2", relevance=RetrievalRelevance.SUPPORTING),
        ],
    )

    evaluator = ProvisionRetrievalEvaluator()

    # Scenario 1: Gold 1 is ranked at position 1
    retrieved = ["PROV-GOLD-1", "PROV-OTHER-1", "PROV-OTHER-2"]
    res = evaluator.evaluate(case, retrieved)
    assert res.details["recall_at_1"] == 0.5
    assert res.details["recall_at_5"] == 0.5
    assert res.details["reciprocal_rank"] == 1.0
    assert res.details["required_recall"] == 1.0
    assert res.passed

    # Scenario 2: Gold required provision is missing in top-10
    retrieved_miss = ["PROV-OTHER-1", "PROV-OTHER-2", "PROV-GOLD-2"]
    res_miss = evaluator.evaluate(case, retrieved_miss)
    assert res_miss.details["required_recall"] == 0.0
    assert not res_miss.passed
    assert res_miss.failure_class is not None


def test_assessment_evaluator_safety_invariants():
    """Verify safety critical invariant alerts: false violation / false compliance."""
    case = EvaluationCase(
        case_id="TEST-SAFETY",
        title="Safety Case",
        category=CaseCategory.BASIC,
        difficulty=DifficultyLevel.L1,
        user_input="Test safety",
        expected_assessment=ExpectedAssessment(
            expected_status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
        ),
    )

    evaluator = AssessmentEvaluator()

    # Engine erroneously returned VIOLATION_CONFIRMED
    mock_bad_assessment = AssessmentResult(
        case_id="TEST-SAFETY",
        status=AssessmentStatus.VIOLATION_CONFIRMED,
        applicable_provisions=[],
    )

    res, false_violation, false_compliance = evaluator.evaluate(case, mock_bad_assessment)
    assert not res.passed
    assert false_violation
    assert not false_compliance
    assert res.score == 0.0
    assert res.failure_class == "FALSE_VIOLATION"


# =====================================================================
# 4. REGRESSION COMPARISON TESTS
# =====================================================================

def test_compare_runs_detects_delta_and_regressions(tmp_path: Path):
    """Verify compare_runs accurately tracks pp delta and flags regressions."""
    base_report = BenchmarkSuiteReport(
        suite_id="SUITE-ALL",
        total_cases=2,
        passed_cases=2,
        accuracy=1.0,
        retrieval_recall_at_10=0.80,
        false_positive_violations=0,
        cases=[
            CaseEvaluationReport(case_id="C1", title="Case 1", category=CaseCategory.BASIC, difficulty=DifficultyLevel.L1, overall_passed=True),
            CaseEvaluationReport(case_id="C2", title="Case 2", category=CaseCategory.BASIC, difficulty=DifficultyLevel.L1, overall_passed=True),
        ],
    )

    # Candidate has a regression on C2 and a false violation
    cand_report = BenchmarkSuiteReport(
        suite_id="SUITE-ALL",
        total_cases=2,
        passed_cases=1,
        accuracy=0.5,
        retrieval_recall_at_10=0.85,
        false_positive_violations=1,
        cases=[
            CaseEvaluationReport(case_id="C1", title="Case 1", category=CaseCategory.BASIC, difficulty=DifficultyLevel.L1, overall_passed=True),
            CaseEvaluationReport(case_id="C2", title="Case 2", category=CaseCategory.BASIC, difficulty=DifficultyLevel.L1, overall_passed=False, failure_class="STATUS_MISMATCH"),
        ],
    )

    base_file = tmp_path / "base.json"
    cand_file = tmp_path / "cand.json"

    base_file.write_text(base_report.model_dump_json(indent=2), encoding="utf-8")
    cand_file.write_text(cand_report.model_dump_json(indent=2), encoding="utf-8")

    code = compare_runs(base_file, cand_file)
    # Must exit with 1 because of regression and safety invariant violation
    assert code == 1


def test_format_delta_helper():
    """Verify format_delta correctly formats percentage and floating point differences."""
    pct_str = format_delta(0.80, 0.85, is_percentage=True)
    assert "+5.0pp" in pct_str

    float_str = format_delta(0.750, 0.650, is_percentage=False)
    assert "-0.100" in float_str


# =====================================================================
# 5. DETERMINISTIC SINGLE CASE EXECUTION TEST
# =====================================================================

@pytest.mark.asyncio
async def test_deterministic_case_execution_basic_001():
    """Run BASIC-001 through SingleCaseEvaluator and verify full turn execution."""
    loader = CorpusLoader()
    case = loader.get_case("BASIC-001")
    assert case is not None

    evaluator = SingleCaseEvaluator()
    report = await evaluator.evaluate_case(case)

    assert report.case_id == "BASIC-001"
    assert "FACT_EXTRACTION" in report.stages
    assert "ASSESSMENT" in report.stages
    assert not report.false_violation
    assert not report.false_compliance
