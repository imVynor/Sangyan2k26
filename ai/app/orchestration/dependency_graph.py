"""Assessment Dependency Graph and Causal Delta Analyzer for SANGYAN.

Epistemic foundation:
- Maps the deterministic causal chain: Fact -> Condition -> Provision -> Finding -> Assessment.
- Enables precise change-detection for incremental retrieval without compromising correctness.
- Generates structured, auditable causal reasons for why an assessment changed.
"""

from typing import Any, Sequence

from ai.app.assessment.contracts import (
    AssessmentResult,
    AssessmentStatus,
    EvidenceItem,
)
from ai.app.case.contracts import AssessmentDelta
from ai.app.evidence_policy.contracts import Claim, ResolvedFieldClaim
from ai.app.retrieval.contracts import RetrievalResponse


class AssessmentDependencyGraph:
    """Tracks causal dependencies between empirical facts and regulatory rules."""

    # Static map of which provisions and dimensions are influenced by specific facts
    FACT_DEPENDENCIES: dict[str, dict[str, Any]] = {
        "transaction_type": {
            "dimension": "trade_specification",
            "provisions": [
                "prov_sebi_dp_max_ceiling",
                "prov_zerodha_tariff_dp_charge",
                "prov_groww_tariff_dp_charge",
            ],
            "conditions": ["transaction_type == equity_delivery"],
            "impact": "Determines whether DP transaction tariffs apply vs intraday/derivative exemptions.",
        },
        "charged_amount": {
            "dimension": "fee_amount",
            "provisions": [
                "prov_sebi_dp_max_ceiling",
                "prov_zerodha_tariff_dp_charge",
                "prov_groww_tariff_dp_charge",
                "prov_sebi_bsda_amc_free",
            ],
            "conditions": ["charged_amount <= max_ceiling", "charged_amount == 0"],
            "impact": "Evaluates statutory ceiling compliance and excessive tariff extraction.",
        },
        "account_type": {
            "dimension": "account_metadata",
            "provisions": [
                "prov_sebi_bsda_amc_free",
                "prov_zerodha_bsda_conditions",
            ],
            "conditions": ["account_type == bsda", "is_bsda == true"],
            "impact": "Determines statutory exemption from Annual Maintenance Charges (AMC).",
        },
        "is_bsda": {
            "dimension": "account_metadata",
            "provisions": [
                "prov_sebi_bsda_amc_free",
                "prov_zerodha_bsda_conditions",
            ],
            "conditions": ["is_bsda == true"],
            "impact": "Triggers statutory zero-AMC protections for Basic Services Demat Accounts.",
        },
        "transaction_date": {
            "dimension": "temporal_validity",
            "provisions": [
                "prov_sebi_dp_circular_2026",
                "prov_sebi_historical_tariff",
            ],
            "conditions": ["valid_from <= transaction_date <= valid_to"],
            "impact": "Resolves regulatory versioning and circular effective dates.",
        },
        "organisation": {
            "dimension": "intermediary_jurisdiction",
            "provisions": [
                "prov_zerodha_tariff_dp_charge",
                "prov_groww_tariff_dp_charge",
                "prov_angelone_tariff",
                "prov_upstox_tariff",
            ],
            "conditions": ["organisation_id == target_organisation"],
            "impact": "Routes to registered depository participant or stock broker tariff schedule.",
        },
    }

    @classmethod
    def detect_affected_dimensions(
        cls,
        old_facts: dict[str, Any],
        new_facts: dict[str, Any],
    ) -> set[str]:
        """Identify which retrieval and assessment dimensions changed between turns."""
        affected: set[str] = set()
        for k, v in new_facts.items():
            if k not in old_facts or old_facts[k] != v:
                affected.add(k)
                if k in cls.FACT_DEPENDENCIES:
                    affected.add(cls.FACT_DEPENDENCIES[k]["dimension"])

        # If facts were removed
        for k in old_facts:
            if k not in new_facts:
                affected.add(k)
                if k in cls.FACT_DEPENDENCIES:
                    affected.add(cls.FACT_DEPENDENCIES[k]["dimension"])

        return affected

    @classmethod
    def build_causal_delta(
        cls,
        case_id: str,
        prev_assessment: AssessmentResult | None,
        new_assessment: AssessmentResult,
        old_facts: dict[str, Any],
        new_facts: dict[str, Any],
        new_evidence: list[EvidenceItem],
        new_claims: list[Claim],
    ) -> AssessmentDelta:
        """Construct an auditable, machine-readable causal delta."""
        prev_status = prev_assessment.status if prev_assessment else None
        new_status = new_assessment.status
        status_changed = (prev_status != new_status)

        # Identify changed facts
        facts_changed = [
            k for k, v in new_facts.items()
            if k not in old_facts or old_facts[k] != v
        ]

        # Identify evidence & claims
        evidence_added = [e.evidence_id for e in new_evidence]
        claims_changed = [c.claim_id for c in new_claims]

        # Provisions added / removed
        prev_evals = {
            p.provision_id: p for p in (prev_assessment.evaluated_provisions if prev_assessment else [])
        }
        new_evals = {p.provision_id: p for p in new_assessment.evaluated_provisions}
        provisions_added = sorted(list(set(new_evals.keys()) - set(prev_evals.keys())))
        provisions_removed = sorted(list(set(prev_evals.keys()) - set(new_evals.keys())))

        # Conditions re-evaluated
        conditions_re_eval = [
            c.condition_id
            for p in new_assessment.evaluated_provisions
            for c in p.conditions
        ]

        # Changed findings / provision outcomes
        findings_changed: list[str] = []
        for pid, eval_res in new_evals.items():
            if pid not in prev_evals:
                findings_changed.append(f"{pid}: NEW -> {eval_res.rule_outcome.value}")
            elif prev_evals[pid].rule_outcome != eval_res.rule_outcome:
                findings_changed.append(
                    f"{pid}: {prev_evals[pid].rule_outcome.value} -> {eval_res.rule_outcome.value}"
                )

        for f in new_assessment.findings:
            findings_changed.append(f"{f.finding_id}: {f.status.value}")

        # Uncertainties resolved / remaining
        prev_missing = {
            req.field_name
            for req in (prev_assessment.evidence_requirements if prev_assessment else [])
            if req.status.value in {"MISSING", "CONTRADICTED"}
        }
        new_missing = {
            req.field_name
            for req in new_assessment.evidence_requirements
            if req.status.value in {"MISSING", "CONTRADICTED"}
        }
        resolved_uncertainties = sorted(list(prev_missing - new_missing))
        remaining_uncertainties = sorted(list(new_missing))

        # Build structured causal narrative
        cause: dict[str, Any] = {
            "facts_changed": facts_changed,
            "old_state": {k: str(old_facts.get(k, "UNKNOWN")) for k in facts_changed},
            "new_state": {k: str(new_facts.get(k)) for k in facts_changed},
            "provisions_affected": provisions_added or list(new_evals.keys()),
        }

        # Causal rationale narrative
        rationale_parts: list[str] = []
        if facts_changed:
            rationale_parts.append(f"Newly established fact(s): {', '.join(facts_changed)}.")
        if resolved_uncertainties:
            rationale_parts.append(f"Resolved requirement(s): {', '.join(resolved_uncertainties)}.")
        if status_changed:
            rationale_parts.append(
                f"Assessment status transitioned from '{prev_status.value if prev_status else 'NONE'}' "
                f"to '{new_status.value}'."
            )
            # Find primary active provision ruling
            for p in new_assessment.evaluated_provisions:
                if p.rule_outcome.value in {"VIOLATED", "SATISFIED"}:
                    cause["primary_finding"] = p.provision_id
                    cause["outcome"] = p.rule_outcome.value
                    rationale_parts.append(
                        f"Primary ruling: Provision '{p.provision_id}' evaluated as {p.rule_outcome.value}."
                    )
                    break
        else:
            rationale_parts.append(f"Assessment status maintained as '{new_status.value}'.")

        cause["causal_narrative"] = " ".join(rationale_parts)

        return AssessmentDelta(
            case_id=case_id,
            previous_status=prev_status,
            new_status=new_status,
            status_changed=status_changed,
            facts_changed=facts_changed,
            claims_changed=claims_changed,
            evidence_added=evidence_added,
            provisions_added=provisions_added,
            provisions_removed=provisions_removed,
            conditions_re_evaluated=conditions_re_eval,
            findings_changed=findings_changed,
            changed_findings=findings_changed,
            new_evidence_ids=evidence_added,
            newly_applicable_provisions=provisions_added,
            newly_inapplicable_provisions=provisions_removed,
            resolved_uncertainties=resolved_uncertainties,
            remaining_uncertainties=remaining_uncertainties,
            clarifications_resolved=resolved_uncertainties,
            clarifications_created=remaining_uncertainties,
            cause=cause,
            rationale=" ".join(rationale_parts),
        )
