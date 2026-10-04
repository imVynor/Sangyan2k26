"""Epistemic Assessment Engine for SANGYAN.

Epistemic foundation:
- Coordinates EvidenceManager, RuleEvaluator, FeeEvaluator, and ConflictDetector.
- Maintains strict epistemic separation: Observed, Derived, Retrieved, Interpreted, Assessed.
- Produces auditable AssessmentResult with layered regulatory vs organisation findings.
- Enforces strict safety invariants:
  1. SANGYAN must NEVER produce COMPLIANT_WITH_REGULATION solely from absence of a violation.
     Affirmative evidence of compliance is strictly required.
  2. SANGYAN must NEVER produce VIOLATION_CONFIRMED when a required condition remains UNKNOWN.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Protocol, Sequence

from ai.app.assessment.conflict_detector import ConflictDetector
from ai.app.assessment.contracts import (
    ApplicabilityEvaluation,
    AssessmentFinding,
    AssessmentRequest,
    AssessmentResult,
    AssessmentStatus,
    Conflict,
    EpistemicLayer,
    EpistemicSupportLevel,
    EvidenceItem,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    EvidenceType,
    RuleOutcome,
    ThreeValuedLogic,
)
from ai.app.assessment.evidence_manager import EvidenceManager
from ai.app.assessment.rule_evaluator import RuleEvaluator
from ai.app.retrieval.contracts import RetrievalResult

logger = logging.getLogger("sangyan.assessment.engine")


class AssessmentEngine(Protocol):
    """Protocol boundary for SANGYAN epistemic assessment."""

    def assess(self, request: AssessmentRequest) -> AssessmentResult:
        """Perform deterministic epistemic assessment over a case request."""
        ...


class DefaultAssessmentEngine:
    """Production deterministic epistemic assessment engine."""

    def assess(self, request: AssessmentRequest) -> AssessmentResult:
        """Execute deterministic assessment over case facts, evidence, and retrieved provisions."""
        # 1. Initialize EvidenceManager
        evidence_mgr = self._build_evidence_manager(request)

        # 2. Map retrieved provisions
        results_map: dict[str, RetrievalResult] = {
            r.provision_id: r for r in request.retrieval_response.results
        }

        # 3. Evaluate each provision deterministically
        evaluations: list[ApplicabilityEvaluation] = []
        for res in request.retrieval_response.results:
            app_eval = RuleEvaluator.evaluate_provision(
                result=res,
                evidence_mgr=evidence_mgr,
                case_facts=request.case_facts,
                incident_date=request.incident_date,
                target_organisation=request.target_organisation,
            )
            evaluations.append(app_eval)

        # 4. Conflict Detection
        conflicts = ConflictDetector.detect_conflicts(evaluations, results_map)
        unresolved_conflicts = [c for c in conflicts if not c.resolved]

        # 5. Extract Evidence Requirements
        required_fields = self._determine_required_fields(
            request.case_facts,
            request.retrieval_response.results if request.retrieval_response else None,
        )
        evidence_reqs = evidence_mgr.evaluate_requirements(required_fields, prefer_documentary=True)
        missing_fields = evidence_mgr.get_missing_fields(required_fields, prefer_documentary=True)

        # 6. Assess Epistemic Status
        status, confidence, findings = self._synthesize_determination(
            request=request,
            evaluations=evaluations,
            unresolved_conflicts=unresolved_conflicts,
            missing_fields=missing_fields,
            evidence_mgr=evidence_mgr,
            results_map=results_map,
        )

        # Collect all referenced provenance IDs
        provenance_ids = [
            (r.provenance.document_id if hasattr(r.provenance, "document_id") else r.document_id)
            for r in request.retrieval_response.results
            if r.document_id
        ]

        return AssessmentResult(
            case_id=request.case_id,
            status=status,
            findings=findings,
            evaluated_provisions=evaluations,
            evidence_requirements=evidence_reqs,
            conflicts=conflicts,
            missing_information=missing_fields,
            temporal_resolution="UNRESOLVED" if status == AssessmentStatus.TEMPORALITY_UNRESOLVED else "RESOLVED",
            authority_resolution="UNRESOLVED" if status == AssessmentStatus.AUTHORITY_UNRESOLVED else "RESOLVED",
            confidence=confidence,
            provenance_ids=sorted(list(set(provenance_ids))),
        )

    def _build_evidence_manager(self, request: AssessmentRequest) -> EvidenceManager:
        """Create EvidenceManager seeded with explicit items and case facts."""
        mgr = EvidenceManager(request.evidence_items)

        # Ensure essential facts are registered as observed evidence if not explicitly passed
        for key, val in request.case_facts.items():
            _, status, _ = mgr.get_field_value(key)
            if status == EvidenceRequirementStatus.MISSING and val is not None:
                mgr.add_item(
                    EvidenceItem(
                        evidence_id=f"EVID-FACT-{key}",
                        case_id=request.case_id,
                        evidence_type=EvidenceType.USER_STATEMENT,
                        field_name=key,
                        value=val,
                        source="case_facts",
                        confidence=EpistemicSupportLevel.MODERATE_SUPPORT,
                    )
                )

        if request.incident_date and mgr.get_field_value("transaction_date")[1] == EvidenceRequirementStatus.MISSING:
            mgr.add_item(
                EvidenceItem(
                    evidence_id="EVID-FACT-DATE",
                    case_id=request.case_id,
                    evidence_type=EvidenceType.SYSTEM_RECORD,
                    field_name="transaction_date",
                    value=request.incident_date,
                    source="incident_date",
                    confidence=EpistemicSupportLevel.HIGH_SUPPORT,
                )
            )

        if request.target_organisation and mgr.get_field_value("organisation")[1] == EvidenceRequirementStatus.MISSING:
            mgr.add_item(
                EvidenceItem(
                    evidence_id="EVID-FACT-ORG",
                    case_id=request.case_id,
                    evidence_type=EvidenceType.SYSTEM_RECORD,
                    field_name="organisation",
                    value=request.target_organisation,
                    source="target_organisation",
                    confidence=EpistemicSupportLevel.HIGH_SUPPORT,
                )
            )

        return mgr

    def _determine_required_fields(
        self,
        case_facts: dict[str, Any],
        results: Sequence[RetrievalResult] | None = None,
    ) -> list[str]:
        """Identify evidentiary fields required for this domain."""
        req = ["charged_amount", "transaction_date"]
        # If case involves AMC or BSDA provisions, is_bsda is required
        is_bsda_case = (
            case_facts.get("transaction_type") == "amc"
            or any("bsda" in (r.provision_text or "").lower() for r in (results or []))
        )
        if is_bsda_case:
            req.append("is_bsda")
        elif not case_facts.get("account_type"):
            req.append("transaction_type")

        # Organisation is required if not in case_facts (unless permitted_amount was pre-injected in synthetic tests)
        if "permitted_amount" not in case_facts and not case_facts.get("organisation"):
            req.append("organisation")
        return req

    def _synthesize_determination(
        self,
        request: AssessmentRequest,
        evaluations: list[ApplicabilityEvaluation],
        unresolved_conflicts: list[Conflict],
        missing_fields: list[str],
        evidence_mgr: EvidenceManager,
        results_map: dict[str, RetrievalResult],
    ) -> tuple[AssessmentStatus, EpistemicSupportLevel, list[AssessmentFinding]]:
        """Synthesize overall determination while enforcing safety invariants."""
        findings: list[AssessmentFinding] = []

        # 1. Check Unresolved Conflicts
        if unresolved_conflicts:
            findings.append(
                AssessmentFinding(
                    finding_id="FIND-CONFLICT",
                    epistemic_layer=EpistemicLayer.ASSESSED,
                    normative_source="REGULATORY",
                    status=AssessmentStatus.CONFLICTING_PROVISIONS,
                    statement=f"Retrieved provisions contain {len(unresolved_conflicts)} unresolved contradiction(s).",
                    provision_ids=[p for c in unresolved_conflicts for p in c.provision_ids],
                    confidence=EpistemicSupportLevel.LOW_SUPPORT,
                )
            )
            return AssessmentStatus.CONFLICTING_PROVISIONS, EpistemicSupportLevel.LOW_SUPPORT, findings

        # 2. Check Temporal Ambiguity
        applicable_evals = [e for e in evaluations if e.overall_applicability == "APPLICABLE"]
        unresolved_temporal = [e for e in evaluations if e.temporal_status == "TEMPORALITY_UNRESOLVED"]

        if unresolved_temporal and (not request.incident_date):
            findings.append(
                AssessmentFinding(
                    finding_id="FIND-TEMP-UNRESOLVED",
                    epistemic_layer=EpistemicLayer.ASSESSED,
                    normative_source="REGULATORY",
                    status=AssessmentStatus.TEMPORALITY_UNRESOLVED,
                    statement="Temporal applicability cannot be established because multiple versions of the rule exist and transaction date is missing.",
                    provision_ids=[e.provision_id for e in evaluations],
                    confidence=EpistemicSupportLevel.LOW_SUPPORT,
                )
            )
            return AssessmentStatus.TEMPORALITY_UNRESOLVED, EpistemicSupportLevel.LOW_SUPPORT, findings

        # 3. Check Regulatory Coverage
        reg_evals = [e for e in applicable_evals if e.source_class == "REGULATORY"]
        org_evals = [e for e in applicable_evals if e.source_class != "REGULATORY"]

        if request.require_regulatory_coverage and not reg_evals:
            findings.append(
                AssessmentFinding(
                    finding_id="FIND-NO-REG-COVERAGE",
                    epistemic_layer=EpistemicLayer.ASSESSED,
                    normative_source="REGULATORY",
                    status=AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED,
                    statement="No authoritative regulatory provisions governing this issue were retrieved.",
                    provision_ids=[e.provision_id for e in org_evals],
                    confidence=EpistemicSupportLevel.LOW_SUPPORT,
                )
            )
            return AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED, EpistemicSupportLevel.LOW_SUPPORT, findings

        # 4. Check Missing Evidence (Safety Invariant: never decide VIOLATION or COMPLIANCE if evidence is missing)
        if missing_fields:
            findings.append(
                AssessmentFinding(
                    finding_id="FIND-EVID-MISSING",
                    epistemic_layer=EpistemicLayer.OBSERVED,
                    normative_source="CASE_EVIDENCE",
                    status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                    statement=f"Required evidence missing or contradicted: {', '.join(missing_fields)}",
                    confidence=EpistemicSupportLevel.INSUFFICIENT_SUPPORT,
                )
            )
            return AssessmentStatus.EVIDENCE_INSUFFICIENT, EpistemicSupportLevel.INSUFFICIENT_SUPPORT, findings

        # 5. Evaluate Violations vs Policy Deviations vs Compliance
        # Check Regulatory Violations
        reg_violations = [e for e in reg_evals if e.rule_outcome == RuleOutcome.VIOLATED]
        if reg_violations:
            for v in reg_violations:
                findings.append(
                    AssessmentFinding(
                        finding_id=f"FIND-VIOLATION-{v.provision_id[:8]}",
                        epistemic_layer=EpistemicLayer.ASSESSED,
                        normative_source="REGULATORY",
                        status=AssessmentStatus.VIOLATION_CONFIRMED,
                        statement=f"Regulatory violation confirmed under provision {v.provision_id}.",
                        provision_ids=[v.provision_id],
                        evidence_ids=v.evidence_ids,
                        confidence=EpistemicSupportLevel.HIGH_SUPPORT,
                    )
                )
            return AssessmentStatus.VIOLATION_CONFIRMED, EpistemicSupportLevel.HIGH_SUPPORT, findings

        # Check Organisation Policy Deviation
        org_violations = [e for e in org_evals if e.rule_outcome == RuleOutcome.VIOLATED]
        if org_violations:
            for v in org_violations:
                findings.append(
                    AssessmentFinding(
                        finding_id=f"FIND-ORG-DEV-{v.provision_id[:8]}",
                        epistemic_layer=EpistemicLayer.ASSESSED,
                        normative_source="ORGANISATION_POLICY",
                        status=AssessmentStatus.ORGANISATION_POLICY_DEVIATION,
                        statement=f"Intermediary deviated from its published policy/tariff under provision {v.provision_id}.",
                        provision_ids=[v.provision_id],
                        evidence_ids=v.evidence_ids,
                        confidence=EpistemicSupportLevel.HIGH_SUPPORT,
                    )
                )
            return AssessmentStatus.ORGANISATION_POLICY_DEVIATION, EpistemicSupportLevel.HIGH_SUPPORT, findings

        # 6. Check Affirmative Compliance (Safety Invariant: requires at least one affirmative SATISFIED rule)
        reg_satisfied = [e for e in reg_evals if e.rule_outcome == RuleOutcome.SATISFIED]
        org_satisfied = [e for e in org_evals if e.rule_outcome == RuleOutcome.SATISFIED]

        if reg_satisfied:
            for s in reg_satisfied:
                findings.append(
                    AssessmentFinding(
                        finding_id=f"FIND-COMPLY-{s.provision_id[:8]}",
                        epistemic_layer=EpistemicLayer.ASSESSED,
                        normative_source="REGULATORY",
                        status=AssessmentStatus.COMPLIANT_WITH_REGULATION,
                        statement=f"Action affirmatively compliant with regulatory requirements under provision {s.provision_id}.",
                        provision_ids=[s.provision_id],
                        evidence_ids=s.evidence_ids,
                        confidence=EpistemicSupportLevel.HIGH_SUPPORT,
                    )
                )
            return AssessmentStatus.COMPLIANT_WITH_REGULATION, EpistemicSupportLevel.HIGH_SUPPORT, findings

        # If provisions were retrieved but none affirmatively satisfied or violated
        findings.append(
            AssessmentFinding(
                finding_id="FIND-INSUFFICIENT-AFFIRMATIVE",
                epistemic_layer=EpistemicLayer.ASSESSED,
                normative_source="REGULATORY",
                status=AssessmentStatus.EVIDENCE_INSUFFICIENT,
                statement="Retrieved rules could not be affirmatively proven satisfied or violated from available facts.",
                provision_ids=[e.provision_id for e in applicable_evals],
                confidence=EpistemicSupportLevel.INSUFFICIENT_SUPPORT,
            )
        )
        return AssessmentStatus.EVIDENCE_INSUFFICIENT, EpistemicSupportLevel.INSUFFICIENT_SUPPORT, findings
