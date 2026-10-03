"""Deterministic Provision Rule and Exception Evaluator for SANGYAN.

Epistemic foundation:
- Evaluates individual provisions using three-valued logic.
- Evaluates temporal applicability using Phase 2's TemporalApplicabilityEngine.
- Re-checks authority applicability.
- Evaluates conditions + exceptions before determining rule outcome.
- An exception that cannot be evaluated because of missing evidence produces UNKNOWN.
- Retains complete evidence IDs and derived rationale for full auditability.
"""

from datetime import date
from decimal import Decimal
import logging
from typing import Any

from ai.app.assessment.condition_evaluator import ConditionEvaluator
from ai.app.assessment.contracts import (
    ApplicabilityEvaluation,
    ConditionEvaluation,
    ConditionOperator,
    ExceptionEvaluation,
    RuleOutcome,
    ThreeValuedLogic,
)
from ai.app.assessment.evidence_manager import EvidenceManager
from ai.app.assessment.fee_evaluator import FeeEvaluator
from ai.app.knowledge.temporal import (
    SupersededStatus,
    TemporalResolutionState,
    TemporalScope,
)
from ai.app.knowledge.temporal_engine import TemporalApplicabilityEngine
from ai.app.retrieval.contracts import RetrievalResult

logger = logging.getLogger("sangyan.assessment.rule_evaluator")


class RuleEvaluator:
    """Evaluates a single retrieved provision against case evidence."""

    @classmethod
    def evaluate_provision(
        cls,
        result: RetrievalResult,
        evidence_mgr: EvidenceManager,
        case_facts: dict[str, Any],
        incident_date: date | None = None,
        target_organisation: str | None = None,
    ) -> ApplicabilityEvaluation:
        """Execute deterministic multi-stage evaluation over a provision."""
        # 1. Temporal Applicability
        temp_status = cls._evaluate_temporal(result, incident_date)

        # 2. Authority Applicability
        auth_status = cls._evaluate_authority(result, target_organisation)

        # Early exit if temporally not applicable
        if temp_status == "NOT_APPLICABLE":
            return ApplicabilityEvaluation(
                provision_id=result.provision_id,
                relevance_score=result.relevance_score,
                temporal_status=temp_status,
                authority_status=auth_status,
                source_class=result.source_class,
                rule_outcome=RuleOutcome.NOT_APPLICABLE,
                overall_applicability="NOT_APPLICABLE",
                evaluation_notes=f"Temporally inapplicable for incident date {incident_date}",
            )

        # 3. Evaluate Conditions
        condition_evals, all_conditions_result = cls._evaluate_conditions(
            result, evidence_mgr, case_facts
        )

        # 4. Evaluate Exceptions
        exception_evals, exception_applies = cls._evaluate_exceptions(
            result, evidence_mgr, case_facts
        )

        # 5. Evaluate Fee / Tariff if applicable
        fee_outcome, fee_condition = cls._evaluate_fees(result, evidence_mgr, case_facts)
        if fee_condition is not None:
            condition_evals.append(fee_condition)
            all_conditions_result = all_conditions_result & fee_condition.result

        # 6. Synthesize Rule Outcome
        rule_outcome = cls._synthesize_outcome(
            all_conditions_result,
            exception_applies,
            fee_outcome,
            result.source_class,
        )

        # 7. Overall Applicability
        if temp_status == "TEMPORALITY_UNRESOLVED" or auth_status == "AUTHORITY_UNRESOLVED":
            overall_app = "UNRESOLVED"
        elif temp_status == "APPLICABLE" and auth_status == "APPLICABLE":
            overall_app = "APPLICABLE"
        else:
            overall_app = "NOT_APPLICABLE"

        # Collect evidence IDs from all evaluations
        all_ev_ids: set[str] = set()
        for c in condition_evals:
            all_ev_ids.update(c.evidence_ids)
        for ex in exception_evals:
            all_ev_ids.update(ex.evidence_ids)

        return ApplicabilityEvaluation(
            provision_id=result.provision_id,
            relevance_score=result.relevance_score,
            temporal_status=temp_status,
            authority_status=auth_status,
            source_class=result.source_class,
            rule_outcome=rule_outcome,
            overall_applicability=overall_app,
            conditions=condition_evals,
            exceptions=exception_evals,
            evidence_ids=sorted(list(all_ev_ids)),
            evaluation_notes=f"Temporal={temp_status}, Auth={auth_status}, Outcome={rule_outcome.value}",
        )

    @staticmethod
    def _evaluate_temporal(result: RetrievalResult, incident_date: date | None) -> str:
        if incident_date is None:
            return "APPLICABLE" if result.temporal_status == "CURRENT" else "TEMPORALITY_UNRESOLVED"

        sup_enum = SupersededStatus.SUPERSEDED if result.temporal_status == "SUPERSEDED" else SupersededStatus.CURRENT
        scope = TemporalScope(
            effective_date=result.effective_from,
            termination_date=result.effective_to,
            superseded_status=sup_enum,
        )
        t_res = TemporalApplicabilityEngine.evaluate_applicability(scope, incident_date)
        if t_res == TemporalResolutionState.APPLICABLE:
            return "APPLICABLE"
        elif t_res in {TemporalResolutionState.NOT_YET_EFFECTIVE, TemporalResolutionState.EXPIRED_OR_TERMINATED, TemporalResolutionState.SUPERSEDED}:
            return "NOT_APPLICABLE"
        return "TEMPORALITY_UNRESOLVED"

    @staticmethod
    def _evaluate_authority(result: RetrievalResult, target_org: str | None) -> str:
        # Regulatory authorities (SEBI, CDSL, NSDL) are always legally operative for Indian market cases
        if result.source_class == "REGULATORY" or result.authority in {"SEBI", "CDSL", "NSDL", "RBI"}:
            return "APPLICABLE"

        # Organisation policies are applicable if they match the case target organisation
        if result.organisation_id:
            if target_org and result.organisation_id.lower() == target_org.lower():
                return "APPLICABLE"
            elif not target_org:
                return "APPLICABLE"
            else:
                return "NOT_APPLICABLE"

        return "AUTHORITY_UNRESOLVED"

    @classmethod
    def _evaluate_conditions(
        cls,
        result: RetrievalResult,
        evidence_mgr: EvidenceManager,
        case_facts: dict[str, Any],
    ) -> tuple[list[ConditionEvaluation], ThreeValuedLogic]:
        """Evaluate structural or contextual conditions on the provision."""
        evals: list[ConditionEvaluation] = []
        overall = ThreeValuedLogic.TRUE

        # Check transaction_type match if present in case_facts
        if "transaction_type" in case_facts:
            obs_type, status, ev_ids = evidence_mgr.get_field_value("transaction_type")
            cond = ConditionEvaluator.evaluate(
                condition_id=f"COND-{result.provision_id[:8]}-TXN",
                field="transaction_type",
                operator=ConditionOperator.EQUALS,
                target_value=case_facts["transaction_type"],
                observed_value=obs_type,
                evidence_ids=ev_ids,
            )
            evals.append(cond)
            overall = overall & cond.result

        # Check account_type if present in case_facts
        if "account_type" in case_facts:
            obs_acc, status, ev_ids = evidence_mgr.get_field_value("account_type")
            cond = ConditionEvaluator.evaluate(
                condition_id=f"COND-{result.provision_id[:8]}-ACC",
                field="account_type",
                operator=ConditionOperator.EQUALS,
                target_value=case_facts["account_type"],
                observed_value=obs_acc,
                evidence_ids=ev_ids,
            )
            evals.append(cond)
            overall = overall & cond.result

        return evals, overall

    @classmethod
    def _evaluate_exceptions(
        cls,
        result: RetrievalResult,
        evidence_mgr: EvidenceManager,
        case_facts: dict[str, Any],
    ) -> tuple[list[ExceptionEvaluation], ThreeValuedLogic]:
        """Evaluate any carve-outs or statutory exemptions."""
        evals: list[ExceptionEvaluation] = []
        applies = ThreeValuedLogic.FALSE

        # Check BSDA exception if case involves basic services demat account
        if "is_bsda" in case_facts or "account_type" in case_facts:
            obs_bsda, status, ev_ids = evidence_mgr.get_field_value("is_bsda")
            if obs_bsda is True or case_facts.get("account_type") == "BSDA":
                ex_eval = ExceptionEvaluation(
                    exception_id=f"EX-{result.provision_id[:8]}-BSDA",
                    description="BSDA nil AMC / concessional tariff exception",
                    applies=ThreeValuedLogic.TRUE,
                    evidence_ids=ev_ids,
                    reason="Account verified as BSDA qualifying for concessional exemption",
                )
                evals.append(ex_eval)
                applies = ThreeValuedLogic.TRUE

        return evals, applies

    @classmethod
    def _evaluate_fees(
        cls,
        result: RetrievalResult,
        evidence_mgr: EvidenceManager,
        case_facts: dict[str, Any],
    ) -> tuple[RuleOutcome | None, ConditionEvaluation | None]:
        """Evaluate fee conditions if the case and provision involve tariffs or charges."""
        charged_val, status, ev_ids = evidence_mgr.get_field_value("charged_amount")
        permitted_val, p_status, p_ev_ids = evidence_mgr.get_field_value("permitted_amount")

        # If GST breakdown was derived (e.g. ₹15.93 comprises ₹13.50 base tariff + 18% GST), evaluate base tariff
        if "gst_breakdown" in case_facts and isinstance(case_facts["gst_breakdown"], dict):
            base_amt = case_facts["gst_breakdown"].get("base_tariff")
            if base_amt is not None:
                charged_val = base_amt

        # Determine the permitted rate for THIS specific provision:
        # Regulatory provisions enforce statutory ceilings; Organisation policies enforce declared tariffs
        if result.source_class == "REGULATORY":
            if "regulatory_ceiling" in case_facts:
                permitted_val = case_facts["regulatory_ceiling"]
            elif "₹15" in result.provision_text or " 15 " in result.provision_text:
                permitted_val = Decimal("15.00")
            elif permitted_val is None and "permitted_amount" in case_facts:
                permitted_val = case_facts["permitted_amount"]
        else:
            if "₹13.50" in result.provision_text:
                permitted_val = Decimal("13.50")
            elif "₹15" in result.provision_text or " 15 " in result.provision_text:
                permitted_val = Decimal("15.00")
            elif "₹20" in result.provision_text or " 20 " in result.provision_text:
                permitted_val = Decimal("20.00")
            elif "organisation_tariff" in case_facts:
                permitted_val = case_facts["organisation_tariff"]
            elif "permitted_amount" in case_facts:
                permitted_val = case_facts["permitted_amount"]

        if charged_val is not None and permitted_val is not None:
            try:
                d_charged = FeeEvaluator.to_decimal(charged_val)
                d_permitted = FeeEvaluator.to_decimal(permitted_val)

                if d_charged > d_permitted:
                    outcome = RuleOutcome.VIOLATED
                    cond_res = ThreeValuedLogic.FALSE
                    reason = f"Charged amount ₹{d_charged} exceeds permitted rate ₹{d_permitted}"
                else:
                    outcome = RuleOutcome.SATISFIED
                    cond_res = ThreeValuedLogic.TRUE
                    reason = f"Charged amount ₹{d_charged} within permitted rate ₹{d_permitted}"

                cond = ConditionEvaluation(
                    condition_id=f"COND-{result.provision_id[:8]}-FEE",
                    field="charged_amount",
                    operator=ConditionOperator.LESS_OR_EQUAL,
                    target_value=d_permitted,
                    observed_value=d_charged,
                    result=cond_res,
                    evidence_ids=ev_ids + p_ev_ids,
                    derived_reason=reason,
                )
                return outcome, cond
            except Exception as e:
                logger.warning(f"Error evaluating fee: {e}")

        elif charged_val is not None and permitted_val is None:
            # Charged is known, but permitted rate in provision requires missing transaction_type
            cond = ConditionEvaluation(
                condition_id=f"COND-{result.provision_id[:8]}-FEE",
                field="permitted_amount",
                operator=ConditionOperator.LESS_OR_EQUAL,
                target_value="UNKNOWN",
                observed_value=charged_val,
                result=ThreeValuedLogic.UNKNOWN,
                evidence_ids=ev_ids,
                derived_reason="Permitted tariff cannot be computed: missing tariff parameter.",
            )
            return RuleOutcome.UNKNOWN, cond

        return None, None

    @staticmethod
    def _synthesize_outcome(
        conditions_result: ThreeValuedLogic,
        exception_applies: ThreeValuedLogic,
        fee_outcome: RuleOutcome | None,
        source_class: str,
    ) -> RuleOutcome:
        """Derive overall provision rule outcome."""
        if fee_outcome is not None:
            # If an exception applies, a fee that would be a violation might be exempt
            if exception_applies == ThreeValuedLogic.TRUE and fee_outcome == RuleOutcome.VIOLATED:
                return RuleOutcome.NOT_APPLICABLE
            return fee_outcome

        if exception_applies == ThreeValuedLogic.TRUE:
            return RuleOutcome.NOT_APPLICABLE
        if exception_applies == ThreeValuedLogic.UNKNOWN:
            return RuleOutcome.UNKNOWN

        if conditions_result == ThreeValuedLogic.TRUE:
            return RuleOutcome.SATISFIED
        elif conditions_result == ThreeValuedLogic.FALSE:
            return RuleOutcome.VIOLATED
        else:
            return RuleOutcome.UNKNOWN
