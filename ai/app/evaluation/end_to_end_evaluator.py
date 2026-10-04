"""End-to-End Evaluation Engine and Benchmark Runner for SANGYAN Phase 4.

Epistemic foundation:
- Runs full end-to-end pipeline:
  Raw User Input -> Fact Extraction -> Case State Integration -> Retrieval -> Assessment -> Generation.
- Evaluates:
  - Fact extraction accuracy
  - Numeric accuracy (Decimal)
  - Date accuracy
  - Entity accuracy
  - Citation correctness
  - Assessment preservation
  - Unsupported claim rate
  - Multilingual extraction accuracy (English, Hindi, Hinglish)
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Sequence
from pydantic import BaseModel, Field

from ai.app.assessment.contracts import (
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
)
from ai.app.assessment.engine import AssessmentEngine, DefaultAssessmentEngine
from ai.app.evaluation.assessment_cases import (
    RES_CDSL_TARIFF,
    RES_HISTORICAL_2026_RULE,
    RES_SEBI_MAX_FEE,
    RES_ZERODHA_TARIFF,
    make_retrieval_result,
)
from ai.app.evaluation.end_to_end_cases import (
    END_TO_END_GOLD_CASES,
    EndToEndGoldCase,
)
from ai.app.extraction.case_integrator import CaseIntegrator
from ai.app.extraction.contracts import FactExtractionRequest, FactExtractionResult
from ai.app.extraction.extractor import FactExtractor
from ai.app.generation.contracts import GeneratedResponse
from ai.app.generation.generator import AuditableResponseGenerator
from ai.app.retrieval.contracts import RetrievalResponse, RetrievalResult

logger = logging.getLogger("sangyan.evaluation.end_to_end")


class EndToEndCaseMetric(BaseModel):
    """Evaluation result for an individual end-to-end benchmark case."""
    case_id: str
    description: str
    language: str
    expected_status: AssessmentStatus
    actual_status: AssessmentStatus
    status_preserved: bool
    expected_fields: dict[str, Any]
    extracted_fields: dict[str, Any]
    extraction_match: bool
    numeric_match: bool
    date_match: bool
    entity_match: bool
    citation_valid: bool
    unsupported_claim: bool
    validation_passed: bool
    contradictions_found: int


class EndToEndBenchmarkSummary(BaseModel):
    """Aggregated end-to-end benchmark evaluation metrics."""
    total_cases: int
    fact_extraction_accuracy: float
    numeric_accuracy: float
    date_accuracy: float
    entity_accuracy: float
    citation_correctness: float
    assessment_preservation: float
    unsupported_claim_rate: float
    multilingual_accuracy: float
    validation_pass_rate: float
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cases: list[EndToEndCaseMetric] = Field(default_factory=list)


class EndToEndEvaluator:
    """Executes gold end-to-end pipeline benchmark evaluation."""

    def __init__(
        self,
        extractor: FactExtractor | None = None,
        assessment_engine: AssessmentEngine | None = None,
        generator: AuditableResponseGenerator | None = None,
    ) -> None:
        self.extractor = extractor or FactExtractor()
        self.assessment_engine = assessment_engine or DefaultAssessmentEngine()
        self.generator = generator or AuditableResponseGenerator()

    def evaluate_all(
        self,
        cases: Sequence[EndToEndGoldCase] | None = None,
    ) -> EndToEndBenchmarkSummary:
        """Run all end-to-end benchmark cases and calculate metrics."""
        gold_cases = list(cases or END_TO_END_GOLD_CASES)
        results: list[EndToEndCaseMetric] = []

        total = len(gold_cases)
        extraction_hits = 0
        numeric_hits = 0
        numeric_total = 0
        date_hits = 0
        date_total = 0
        entity_hits = 0
        entity_total = 0
        status_hits = 0
        citation_hits = 0
        validation_hits = 0
        unsupported_claims = 0
        ml_hits = 0
        ml_total = 0

        for case in gold_cases:
            # Step 1: Fact Extraction
            ext_req = FactExtractionRequest(
                input_text=case.raw_input,
                source_id=case.source_id,
                source_type=case.source_type,
                reference_date=case.reference_date,
                language=case.language,
            )
            ext_res: FactExtractionResult = self.extractor.extract(ext_req)

            # Step 2: Case State Integration
            ev_items, case_facts, warnings = CaseIntegrator.integrate_proposals(
                extraction_result=ext_res,
                case_id=case.case_id,
            )

            # Step 3: Retrieval Setup
            retrieval_resp = self._resolve_retrieval_context(case, case_facts)

            # Step 4: Epistemic Assessment
            incident_dt = case_facts.get("transaction_date")
            target_org = case.target_organisation or case_facts.get("organisation")

            req = AssessmentRequest(
                case_id=case.case_id,
                case_facts=case_facts,
                evidence_items=ev_items,
                retrieval_response=retrieval_resp,
                incident_date=incident_dt,
                target_organisation=target_org,
                require_regulatory_coverage=True,
            )
            assess_res: AssessmentResult = self.assessment_engine.assess(req)

            # Step 5: Auditable Response Generation
            gen_resp: GeneratedResponse = self.generator.generate_response(
                assessment=assess_res,
                retrieval=retrieval_resp,
                evidence_items=ev_items,
                case_facts=case_facts,
            )

            # Step 6: Verify Metrics
            # Fact Extraction Match
            ext_ok = True
            for k, exp_v in case.expected_extracted_fields.items():
                act_v = case_facts.get(k)
                if act_v != exp_v:
                    ext_ok = False
            if ext_ok:
                extraction_hits += 1

            # Sub-field metrics
            num_ok = True
            if "charged_amount" in case.expected_extracted_fields:
                numeric_total += 1
                if case_facts.get("charged_amount") == case.expected_extracted_fields["charged_amount"]:
                    numeric_hits += 1
                else:
                    num_ok = False

            dt_ok = True
            if "transaction_date" in case.expected_extracted_fields:
                date_total += 1
                if case_facts.get("transaction_date") == case.expected_extracted_fields["transaction_date"]:
                    date_hits += 1
                else:
                    dt_ok = False

            ent_ok = True
            if "organisation" in case.expected_extracted_fields:
                entity_total += 1
                if case_facts.get("organisation") == case.expected_extracted_fields["organisation"]:
                    entity_hits += 1
                else:
                    ent_ok = False

            # Status preservation
            status_ok = assess_res.status == case.expected_assessment_status and gen_resp.assessment_status == case.expected_assessment_status
            if status_ok:
                status_hits += 1

            # Validation & citation
            val_ok = gen_resp.validation_passed
            if val_ok:
                validation_hits += 1

            cit_ok = len(gen_resp.regulatory_basis) > 0 and all(c.is_validated for c in gen_resp.regulatory_basis)
            if cit_ok:
                citation_hits += 1

            has_unsupported = any("UNSUPPORTED_CLAIM" in e for e in gen_resp.validation_errors)
            if has_unsupported:
                unsupported_claims += 1

            # Multilingual
            if case.language in {"hi", "hinglish"}:
                ml_total += 1
                if ext_ok and status_ok:
                    ml_hits += 1

            results.append(
                EndToEndCaseMetric(
                    case_id=case.case_id,
                    description=case.description,
                    language=case.language,
                    expected_status=case.expected_assessment_status,
                    actual_status=assess_res.status,
                    status_preserved=status_ok,
                    expected_fields=case.expected_extracted_fields,
                    extracted_fields=case_facts,
                    extraction_match=ext_ok,
                    numeric_match=num_ok,
                    date_match=dt_ok,
                    entity_match=ent_ok,
                    citation_valid=cit_ok,
                    unsupported_claim=has_unsupported,
                    validation_passed=val_ok,
                    contradictions_found=len(ext_res.contradictions),
                )
            )

        return EndToEndBenchmarkSummary(
            total_cases=total,
            fact_extraction_accuracy=extraction_hits / total if total else 0.0,
            numeric_accuracy=numeric_hits / numeric_total if numeric_total else 1.0,
            date_accuracy=date_hits / date_total if date_total else 1.0,
            entity_accuracy=entity_hits / entity_total if entity_total else 1.0,
            citation_correctness=citation_hits / total if total else 0.0,
            assessment_preservation=status_hits / total if total else 0.0,
            unsupported_claim_rate=unsupported_claims / total if total else 0.0,
            multilingual_accuracy=ml_hits / ml_total if ml_total else 1.0,
            validation_pass_rate=validation_hits / total if total else 0.0,
            cases=results,
        )

    def _resolve_retrieval_context(
        self,
        case: EndToEndGoldCase,
        case_facts: dict[str, Any],
    ) -> RetrievalResponse:
        """Resolve authoritative provisions governing this end-to-end case."""
        # 1. Historical dispute case
        if case.case_id == "E2E-07":
            return RetrievalResponse(
                results=[RES_HISTORICAL_2026_RULE],
                total_candidates_found=1,
            )

        # 2. Regulatory coverage gap (algo trading)
        if case.case_id == "E2E-09":
            return RetrievalResponse(
                results=[RES_ZERODHA_TARIFF],
                total_candidates_found=1,
            )

        # 3. Layered multi-normative cases (Zerodha)
        if case.target_organisation == "ORG_ZERODHA":
            return RetrievalResponse(
                results=[RES_SEBI_MAX_FEE, RES_ZERODHA_TARIFF],
                total_candidates_found=2,
            )

        # 4. ICICI Direct / CDSL case
        if case.target_organisation == "ORG_ICICIDIRECT":
            return RetrievalResponse(
                results=[RES_CDSL_TARIFF],
                total_candidates_found=1,
            )

        # 5. Default statutory DP fee ceiling
        return RetrievalResponse(
            results=[RES_SEBI_MAX_FEE],
            total_candidates_found=1,
        )

    def save_report(
        self,
        summary: EndToEndBenchmarkSummary,
        output_path: Path | str = "ai/corpus/end_to_end_benchmark_report.json",
    ) -> Path:
        """Persist report to JSON."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(summary.model_dump_json(indent=2))
        return path
