"""Evidence Policy Resolver and Authority Engine for SANGYAN.

Epistemic foundation:
- Replaces coarse universal rules with field-specific authority policies.
- Preserves all conflicting claims across dialogue turns.
- Resolves operative facts according to explicit evidentiary precedence.
- If two authoritative documents of equal rank disagree, produces CONTRADICTED.
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Sequence
import uuid

from ai.app.assessment.contracts import EvidenceItem, EvidenceType
from ai.app.evidence_policy.contracts import (
    Claim,
    ClaimStatus,
    EvidenceAuthorityScope,
    EvidenceResolutionPolicy,
    ResolvedFieldClaim,
)

logger = logging.getLogger("sangyan.evidence_policy.resolver")


class EvidencePolicyRegistry:
    """Configurable registry of field-specific evidence precedence policies."""

    def __init__(self, policies: list[EvidenceResolutionPolicy] | None = None) -> None:
        self._policies: dict[str, EvidenceResolutionPolicy] = {}
        defaults = policies or self._default_policies()
        for p in defaults:
            self.register(p)

    def register(self, policy: EvidenceResolutionPolicy) -> None:
        self._policies[policy.field_name] = policy

    def get(self, field_name: str) -> EvidenceResolutionPolicy | None:
        return self._policies.get(field_name)

    @classmethod
    def _default_policies(cls) -> list[EvidenceResolutionPolicy]:
        return [
            EvidenceResolutionPolicy(
                policy_id="POL-CHARGED-AMOUNT",
                field_name="charged_amount",
                authority_scope=EvidenceAuthorityScope.FINANCIAL_TARIFF,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.TRANSACTION_RECORD,
                    EvidenceType.BROKER_STATEMENT,
                    EvidenceType.INVOICE,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Broker contract notes and transaction records supersede investor recollection for charged fee amounts.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-TRANSACTION-DATE",
                field_name="transaction_date",
                authority_scope=EvidenceAuthorityScope.TEMPORAL_RECORD,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.TRANSACTION_RECORD,
                    EvidenceType.BROKER_STATEMENT,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Trade settlement dates on official statements supersede user memory.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-TRANSACTION-TYPE",
                field_name="transaction_type",
                authority_scope=EvidenceAuthorityScope.TRADE_SPECIFICATION,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.TRANSACTION_RECORD,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Contract note trade classifications (delivery vs intraday) take precedence over narrative claims.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-ACCOUNT-TYPE",
                field_name="account_type",
                authority_scope=EvidenceAuthorityScope.ACCOUNT_METADATA,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.BROKER_STATEMENT,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Client master profile and ledger statement take precedence for account category (e.g. BSDA vs regular).",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-IS-BSDA",
                field_name="is_bsda",
                authority_scope=EvidenceAuthorityScope.ACCOUNT_METADATA,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.BROKER_STATEMENT,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Depository or broker statement takes precedence for BSDA eligibility.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-ORGANISATION",
                field_name="organisation",
                authority_scope=EvidenceAuthorityScope.ACCOUNT_METADATA,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.TRANSACTION_RECORD,
                    EvidenceType.BROKER_STATEMENT,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Verified account statement / contract note supersedes user assertion for intermediary identity.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-CHARGE-TYPE",
                field_name="charge_type",
                authority_scope=EvidenceAuthorityScope.FINANCIAL_TARIFF,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.TRANSACTION_RECORD,
                    EvidenceType.BROKER_STATEMENT,
                    EvidenceType.INVOICE,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Official contract notes and ledgers supersede user categorization of fee or charge type for the charge event.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-FEE-TYPE",
                field_name="fee_type",
                authority_scope=EvidenceAuthorityScope.FINANCIAL_TARIFF,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.TRANSACTION_RECORD,
                    EvidenceType.BROKER_STATEMENT,
                    EvidenceType.INVOICE,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Official statements supersede user recollection for fee type.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-ORDER-VALUE",
                field_name="order_value",
                authority_scope=EvidenceAuthorityScope.TRADE_SPECIFICATION,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.TRANSACTION_RECORD,
                    EvidenceType.BROKER_STATEMENT,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Contract note trade order value supersedes user assertion.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-PORTFOLIO-VALUE",
                field_name="portfolio_value",
                authority_scope=EvidenceAuthorityScope.ACCOUNT_METADATA,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.BROKER_STATEMENT,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="CONTRADICTED",
                description="Holding statement / depository statement supersedes user assertion for portfolio holding value.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-USER-INTENT",
                field_name="user_intent",
                authority_scope=EvidenceAuthorityScope.SUBJECTIVE_EXPERIENCE,
                precedence=[
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="LATEST",
                description="User statement is primary evidence for user intent.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-SUBJECTIVE-DESCRIPTION",
                field_name="subjective_description",
                authority_scope=EvidenceAuthorityScope.SUBJECTIVE_EXPERIENCE,
                precedence=[
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="LATEST",
                description="User narrative is primary evidence for subjective description.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-USER-EXPERIENCE",
                field_name="user_experience",
                authority_scope=EvidenceAuthorityScope.SUBJECTIVE_EXPERIENCE,
                precedence=[
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="LATEST",
                description="Citizen statement is primary evidence for personal grievance experience.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-SUPPORT-CONTACT",
                field_name="support_contact",
                authority_scope=EvidenceAuthorityScope.COMMUNICATION_HISTORY,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="SUPPORTED",
                description="Support tickets, emails, and user statements establish customer support contacts.",
            ),
            EvidenceResolutionPolicy(
                policy_id="POL-PLATFORM-OUTAGE",
                field_name="platform_outage",
                authority_scope=EvidenceAuthorityScope.SERVICE_OUTAGE,
                precedence=[
                    EvidenceType.DOCUMENT,
                    EvidenceType.TRANSACTION_RECORD,
                    EvidenceType.USER_STATEMENT,
                ],
                tie_breaker="SUPPORTED",
                description="Technical logs and investor outage reports establish platform downtime.",
            ),
        ]


class EvidencePolicyResolver:
    """Evaluates claims for a field using registered policies."""

    def __init__(self, registry: EvidencePolicyRegistry | None = None) -> None:
        self.registry = registry or EvidencePolicyRegistry()

    @classmethod
    def default(cls) -> "EvidencePolicyResolver":
        return cls(registry=EvidencePolicyRegistry())

    def build_claims_from_evidence(
        self,
        evidence_items: Sequence[EvidenceItem],
        case_id: str | None = None,
    ) -> list[Claim]:
        """Convert EvidenceItem sequence into structured Claims."""
        claims: list[Claim] = []
        for ev in evidence_items:
            claim_text = getattr(ev, "raw_quote", None) or f"{ev.field_name} = {ev.value}"
            source_id = ""
            if isinstance(ev.provenance, dict):
                source_id = str(ev.provenance.get("source_id", ev.source))
            elif ev.provenance:
                source_id = str(getattr(ev.provenance, "source_id", ev.source))
            else:
                source_id = ev.source

            claim = Claim(
                claim_id=f"CLM-{uuid.uuid4().hex[:8].upper()}",
                case_id=case_id,
                field_name=ev.field_name,
                claim_text=claim_text,
                claimed_value=ev.value,
                source_type=getattr(ev, "evidence_type", EvidenceType.USER_STATEMENT),
                source_id=source_id,
                evidence_ids=[ev.evidence_id],
                status=ClaimStatus.UNRESOLVED,
            )
            claims.append(claim)
        return claims

    def resolve_field(
        self,
        field_name: str,
        evidence_items: Sequence[EvidenceItem],
        existing_claims: Sequence[Claim] | None = None,
    ) -> ResolvedFieldClaim:
        """Resolve operative value and reconcile conflicting claims for a field."""
        # 1. Gather all claims for this field
        relevant_items = [e for e in evidence_items if e.field_name == field_name]
        claims = [c for c in (existing_claims or []) if c.field_name == field_name]

        # If claims not already constructed, build from evidence items
        if not claims and relevant_items:
            claims = self.build_claims_from_evidence(relevant_items)
        elif relevant_items:
            # Sync any new evidence items into claims
            existing_ev_ids = {ev_id for c in claims for ev_id in c.evidence_ids}
            for item in relevant_items:
                if item.evidence_id not in existing_ev_ids:
                    claims.extend(self.build_claims_from_evidence([item]))

        if not claims:
            return ResolvedFieldClaim(
                field_name=field_name,
                operative_value=None,
                status=ClaimStatus.UNRESOLVED,
                resolution_rationale=f"No evidence or claims provided for field '{field_name}'.",
            )

        # 2. Check if all claims agree
        first_val = claims[0].claimed_value
        all_equal = all(self._values_equal(first_val, c.claimed_value) for c in claims)
        if all_equal:
            for c in claims:
                c.status = ClaimStatus.SUPPORTED
            return ResolvedFieldClaim(
                field_name=field_name,
                operative_value=first_val,
                status=ClaimStatus.SUPPORTED,
                active_claim_id=claims[0].claim_id,
                supporting_claim_ids=[c.claim_id for c in claims],
                all_claims=claims,
                resolution_rationale=f"All {len(claims)} claim(s) agree on value '{first_val}'.",
            )

        # 3. Disagreement exists: Consult Field Policy
        policy = self.registry.get(field_name)
        if not policy:
            # Without an explicit policy, cannot arbitrate conflicting values
            for c in claims:
                c.status = ClaimStatus.CONTRADICTED
            return ResolvedFieldClaim(
                field_name=field_name,
                operative_value=None,
                status=ClaimStatus.CONTRADICTED,
                all_claims=claims,
                contradicting_claim_ids=[c.claim_id for c in claims],
                resolution_rationale=f"Conflicting values detected for '{field_name}' with no governing policy.",
            )

        # 4. Group claims by policy precedence rank
        ranked_groups: dict[int, list[Claim]] = defaultdict(list)
        unranked: list[Claim] = []
        for c in claims:
            if c.source_type in policy.precedence:
                rank = policy.precedence.index(c.source_type)
                ranked_groups[rank].append(c)
            else:
                unranked.append(c)

        if not ranked_groups:
            for c in claims:
                c.status = ClaimStatus.CONTRADICTED
            return ResolvedFieldClaim(
                field_name=field_name,
                operative_value=None,
                status=ClaimStatus.CONTRADICTED,
                all_claims=claims,
                contradicting_claim_ids=[c.claim_id for c in claims],
                applied_policy_id=policy.policy_id,
                resolution_rationale=f"Claims for '{field_name}' do not match precedence types in policy '{policy.policy_id}'.",
            )

        # 5. Check highest priority group
        best_rank = min(ranked_groups.keys())
        best_claims = ranked_groups[best_rank]
        best_source_type = policy.precedence[best_rank]

        # Check if multiple user statements represent sequential corrections
        if best_source_type == EvidenceType.USER_STATEMENT and len(best_claims) > 1:
            latest_claim = best_claims[-1]
            earlier_claims = best_claims[:-1]
            latest_claim.status = ClaimStatus.RESOLVED_BY_POLICY
            for ec in earlier_claims:
                ec.status = ClaimStatus.CONTRADICTED

            return ResolvedFieldClaim(
                field_name=field_name,
                operative_value=latest_claim.claimed_value,
                status=ClaimStatus.RESOLVED_BY_POLICY,
                active_claim_id=latest_claim.claim_id,
                supporting_claim_ids=[latest_claim.claim_id],
                contradicting_claim_ids=[c.claim_id for c in earlier_claims],
                all_claims=claims,
                applied_policy_id=policy.policy_id,
                resolution_rationale=(
                    f"Sequential user correction: Operative value '{latest_claim.claimed_value}' "
                    f"supersedes prior assertions for '{field_name}'."
                ),
            )

        # 6. Check if the highest priority group itself has conflicting values
        first_best_val = best_claims[0].claimed_value
        best_all_equal = all(self._values_equal(first_best_val, c.claimed_value) for c in best_claims)

        if not best_all_equal:
            # Highest priority documentary sources disagree among themselves!
            # e.g. Contract Note 1 says ₹15, Contract Note 2 says ₹20.
            # Must NOT arbitrate: strictly CONTRADICTED.
            for c in claims:
                c.status = ClaimStatus.CONTRADICTED
            return ResolvedFieldClaim(
                field_name=field_name,
                operative_value=None,
                status=ClaimStatus.CONTRADICTED,
                all_claims=claims,
                contradicting_claim_ids=[c.claim_id for c in claims],
                applied_policy_id=policy.policy_id,
                resolution_rationale=(
                    f"Irreconcilable conflict: Multiple {best_source_type.value} sources "
                    f"assert contradictory values for '{field_name}'."
                ),
            )

        # 7. Precedence Resolution: Documentary/authoritative source takes precedence over lower tier (e.g. user assertion)
        operative_val = first_best_val
        supporting_ids: list[str] = []
        contradicting_ids: list[str] = []

        for c in claims:
            if self._values_equal(c.claimed_value, operative_val):
                c.status = ClaimStatus.SUPPORTED
                supporting_ids.append(c.claim_id)
            else:
                c.status = ClaimStatus.CONTRADICTED
                contradicting_ids.append(c.claim_id)

        # Mark active claim as resolved by policy
        best_claims[0].status = ClaimStatus.RESOLVED_BY_POLICY

        rationale = (
            f"Policy '{policy.policy_id}' resolved operative value to '{operative_val}' "
            f"via authoritative {best_source_type.value} evidence, preserving {len(contradicting_ids)} "
            f"contradictory claim(s)."
        )

        return ResolvedFieldClaim(
            field_name=field_name,
            operative_value=operative_val,
            status=ClaimStatus.RESOLVED_BY_POLICY,
            active_claim_id=best_claims[0].claim_id,
            supporting_claim_ids=supporting_ids,
            contradicting_claim_ids=contradicting_ids,
            all_claims=claims,
            applied_policy_id=policy.policy_id,
            resolution_rationale=rationale,
        )

    def reconcile_claims(
        self,
        existing_claims: Sequence[Claim],
        new_evidence: Sequence[EvidenceItem] | None = None,
        field_policy: EvidenceResolutionPolicy | None = None,
    ) -> ResolvedFieldClaim:
        """Reconcile existing claims with any new evidence items under a governing policy (Step 3)."""
        if not existing_claims and not new_evidence:
            return ResolvedFieldClaim(
                field_name="unknown",
                operative_value=None,
                status=ClaimStatus.UNRESOLVED,
                resolution_rationale="No claims or evidence provided for reconciliation.",
            )
        field_name = existing_claims[0].field_name if existing_claims else new_evidence[0].field_name
        if field_policy:
            self.registry.register(field_policy)
        evidence_items = list(new_evidence or [])
        return self.resolve_field(
            field_name=field_name,
            evidence_items=evidence_items,
            existing_claims=existing_claims,
        )

    def _values_equal(self, a: Any, b: Any) -> bool:
        """Deterministic equivalence check handling Decimal, float, and case normalization."""
        if a == b:
            return True
        if a is None or b is None:
            return False
        # Decimal / numeric comparison
        try:
            ca = str(a).replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
            cb = str(b).replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
            da = Decimal(ca)
            db = Decimal(cb)
            return da == db
        except Exception:
            pass
        # Normalized string comparison
        sa = str(a).strip().lower()
        sb = str(b).strip().lower()
        if sa == sb:
            return True
        # Semantic equivalence for charge types and delivery transactions
        delivery_synonyms = {"equity_delivery", "equity_delivery_sell", "equity_delivery_buy"}
        if sa in delivery_synonyms and sb in delivery_synonyms:
            return True
        dp_synonyms = {"dp_charge", "dp_charges", "depository_participant_charges"}
        if sa in dp_synonyms and sb in dp_synonyms:
            return True
        return False
