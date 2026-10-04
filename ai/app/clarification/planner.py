"""Deterministic Clarification Planner for SANGYAN Multi-Turn Dialogue.

Epistemic foundation:
- Calculates the smallest set of high-value missing requirements.
- Never asks for already established facts.
- Respects user declinations (USER_DECLINED fields are never re-asked).
- Prioritizes questions by potential to shift assessment state (Information Gain).
- Contradiction-aware: targets specific conflicting values rather than asking generic questions.
- Generates language-independent field targets with English, Hindi, and Hinglish renderings.
"""

from decimal import Decimal
import logging
from typing import Any, Sequence

from ai.app.assessment.contracts import (
    AssessmentResult,
    AssessmentStatus,
    EvidenceItem,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    EvidenceType,
)
from ai.app.assessment.evidence_manager import EvidenceManager
from ai.app.case.contracts import CaseState
from ai.app.clarification.contracts import (
    ClarificationPlan,
    ClarificationPlanStatus,
    ClarificationQuestion,
    QuestionPriority,
)

logger = logging.getLogger("sangyan.clarification.planner")

# Canonical Multilingual Question Library
CANONICAL_QUESTIONS: dict[str, dict[str, Any]] = {
    "transaction_type": {
        "reason": "Statutory Depository Participant (DP) fee caps apply specifically to delivery sales and do not apply to intraday trades.",
        "priority": QuestionPriority.CRITICAL,
        "expected_answer_type": "ENUM",
        "acceptable_values": ["equity_delivery", "intraday", "mutual_fund", "pledge"],
        "acceptable_evidence_types": [EvidenceType.USER_STATEMENT, EvidenceType.DOCUMENT, EvidenceType.TRANSACTION_RECORD],
        "en": "Was this transaction an equity delivery sale (shares held in demat) or an intraday trade?",
        "hi": "क्या यह लेन-देन इक्विटी डिलीवरी बिक्री (डीमैट में रखे शेयर) थी या इंट्राडे ट्रेड?",
        "hinglish": "Ye transaction delivery sale tha ya intraday trade?",
    },
    "transaction_date": {
        "reason": "The applicable regulatory circular and fee ceiling depend on the date the transaction occurred.",
        "priority": QuestionPriority.HIGH,
        "expected_answer_type": "DATE",
        "acceptable_values": None,
        "acceptable_evidence_types": [EvidenceType.USER_STATEMENT, EvidenceType.DOCUMENT, EvidenceType.TRANSACTION_RECORD],
        "en": "On what date did this transaction or fee deduction take place?",
        "hi": "यह लेन-देन या शुल्क कटौती किस तारीख को हुई थी?",
        "hinglish": "Ye transaction ya fee deduction kis date ko hua tha?",
    },
    "charged_amount": {
        "reason": "The exact fee amount is required to evaluate against the statutory tariff ceiling.",
        "priority": QuestionPriority.CRITICAL,
        "expected_answer_type": "DECIMAL",
        "acceptable_values": None,
        "acceptable_evidence_types": [EvidenceType.USER_STATEMENT, EvidenceType.DOCUMENT, EvidenceType.TRANSACTION_RECORD],
        "en": "What exact amount (in INR) was deducted by the intermediary?",
        "hi": "मध्यस्थ द्वारा कितनी सटीक राशि (रुपये में) काटी गई थी?",
        "hinglish": "Broker ne exact kitna amount (INR mein) deduct kiya tha?",
    },
    "organisation": {
        "reason": "The intermediary must be identified to check their specific depository association and policy schedule.",
        "priority": QuestionPriority.HIGH,
        "expected_answer_type": "STRING",
        "acceptable_values": ["Zerodha", "Angel One", "Groww", "Upstox", "ICICI Direct"],
        "acceptable_evidence_types": [EvidenceType.USER_STATEMENT, EvidenceType.DOCUMENT],
        "en": "Which stock broker or depository participant handled this transaction?",
        "hi": "किस स्टॉक ब्रोकर या डिपॉजिटरी पार्टिसिपेंट ने यह लेन-देन संभाला था?",
        "hinglish": "Kaunse broker ya DP ne ye transaction kiya tha?",
    },
    "is_bsda": {
        "reason": "Basic Services Demat Accounts (BSDA) have statutory exemptions from Annual Maintenance Charges under SEBI circulars.",
        "priority": QuestionPriority.HIGH,
        "expected_answer_type": "BOOLEAN",
        "acceptable_values": ["true", "false"],
        "acceptable_evidence_types": [EvidenceType.USER_STATEMENT, EvidenceType.DOCUMENT],
        "en": "Is this demat account registered as a Basic Services Demat Account (BSDA)?",
        "hi": "क्या यह डीमैट खाता बेसिक सर्विसेज डीमैट अकाउंट (BSDA) के रूप में पंजीकृत है?",
        "hinglish": "Kya ye account BSDA (Basic Services Demat Account) category mein hai?",
    },
    "contract_note": {
        "reason": "A contract note or ledger entry provides definitive documentary proof for fee reconciliation.",
        "priority": QuestionPriority.MEDIUM,
        "expected_answer_type": "DOCUMENT",
        "acceptable_values": None,
        "acceptable_evidence_types": [EvidenceType.DOCUMENT, EvidenceType.TRANSACTION_RECORD],
        "en": "Can you provide or upload the contract note or broker ledger statement for this trade?",
        "hi": "क्या आप इस ट्रेड के लिए कॉन्ट्रैक्ट नोट या ब्रोकर लेज़र स्टेटमेंट प्रदान कर सकते हैं?",
        "hinglish": "Kya aap is trade ka contract note ya ledger statement share kar sakte hain?",
    },
}


class ClarificationPlanner:
    """Plans minimal, high-value clarification questions for an investor grievance."""

    def __init__(self, max_questions_per_turn: int = 3, max_rounds: int = 5) -> None:
        self.max_questions_per_turn = max_questions_per_turn
        self.max_rounds = max_rounds

    def plan(
        self,
        case_state: CaseState,
        assessment_result: AssessmentResult,
        language: str = "en",
    ) -> ClarificationPlan:
        """Deterministically determine the next clarification questions or terminal status."""
        plan_id = f"PLAN-{case_state.version}"
        current_round = case_state.clarification_rounds + 1

        # 1. Terminal Check: If assessment is already definitive, no questions required
        if assessment_result.status in {
            AssessmentStatus.VIOLATION_CONFIRMED,
            AssessmentStatus.COMPLIANT_WITH_REGULATION,
            AssessmentStatus.ORGANISATION_POLICY_DEVIATION,
            AssessmentStatus.CONFLICTING_PROVISIONS,
        }:
            return ClarificationPlan(
                plan_id=plan_id,
                case_id=case_state.case_id,
                case_version=case_state.version,
                questions=[],
                status=ClarificationPlanStatus.RESOLVED,
                round_number=current_round,
                rationale="Assessment status is definitive; no additional evidentiary clarification required.",
            )

        # 2. Terminal Check: Clarification Round Limits
        if case_state.clarification_rounds >= self.max_rounds:
            logger.info(f"Case '{case_state.case_id}' reached maximum clarification rounds ({self.max_rounds}).")
            return ClarificationPlan(
                plan_id=plan_id,
                case_id=case_state.case_id,
                case_version=case_state.version,
                questions=[],
                status=ClarificationPlanStatus.MAX_CLARIFICATIONS_REACHED,
                round_number=current_round,
                rationale=f"Maximum clarification rounds ({self.max_rounds}) reached. Concluding with available evidence.",
            )

        # 3. Check for Active Contradictions in Evidence
        ev_manager = EvidenceManager(case_state.evidence)
        contradicted_questions: list[ClarificationQuestion] = []
        for req in assessment_result.evidence_requirements:
            val, status, ev_ids = ev_manager.get_field_value(req.field_name)
            if req.status == EvidenceRequirementStatus.CONTRADICTED or status == EvidenceRequirementStatus.CONTRADICTED:
                # Find the contradictory values
                matching_items = [e for e in case_state.evidence if e.field_name == req.field_name]
                sample_vals = [f"'{m.value}' from {m.source}" for m in matching_items[:2]]
                vals_str = " and ".join(sample_vals)
                
                en_q = (
                    f"We found conflicting values for {req.field_name.replace('_', ' ')}: {vals_str}. "
                    f"Which value is shown on your official contract note or bank ledger?"
                )
                hi_q = (
                    f"हमें {req.field_name} के लिए विरोधाभासी मान मिले: {vals_str}। "
                    f"आपके आधिकारिक कॉन्ट्रैक्ट नोट में कौन सा मान दिखाया गया है?"
                )
                hinglish_q = (
                    f"{req.field_name} ke liye conflicting values mili hain: {vals_str}. "
                    f"Official contract note pe kaunsa value printed hai?"
                )

                q_text = hi_q if language == "hi" else (hinglish_q if language == "hinglish" else en_q)
                contradicted_questions.append(
                    ClarificationQuestion(
                        field=req.field_name,
                        question=q_text,
                        reason=f"Evidence contains conflicting assertions ({vals_str}) that must be reconciled.",
                        required_for=[f"CONTRADICTION_{req.field_name}"],
                        priority=QuestionPriority.CRITICAL,
                        expected_answer_type="STRING",
                        acceptable_evidence_types=[EvidenceType.DOCUMENT, EvidenceType.TRANSACTION_RECORD],
                        multilingual_text={"en": en_q, "hi": hi_q, "hinglish": en_q},
                    )
                )

        if contradicted_questions:
            return ClarificationPlan(
                plan_id=plan_id,
                case_id=case_state.case_id,
                case_version=case_state.version,
                questions=contradicted_questions[: self.max_questions_per_turn],
                status=ClarificationPlanStatus.QUESTIONS_REQUIRED,
                round_number=current_round,
                rationale="Targeting evidentiary contradictions before re-evaluating applicable rules.",
            )

        # 4. Check Temporal Ambiguity
        if assessment_result.status == AssessmentStatus.TEMPORALITY_UNRESOLVED:
            if "transaction_date" not in case_state.facts and "transaction_date" not in case_state.declined_fields:
                spec = CANONICAL_QUESTIONS["transaction_date"]
                q_text = spec.get(language, spec["en"])
                q = ClarificationQuestion(
                    field="transaction_date",
                    question=q_text,
                    reason="Applicable statutory circulars changed over time. The exact date establishes which circular governed.",
                    priority=QuestionPriority.CRITICAL,
                    expected_answer_type="DATE",
                    acceptable_evidence_types=spec["acceptable_evidence_types"],
                    multilingual_text={"en": spec["en"], "hi": spec["hi"], "hinglish": spec["hinglish"]},
                )
                return ClarificationPlan(
                    plan_id=plan_id,
                    case_id=case_state.case_id,
                    case_version=case_state.version,
                    questions=[q],
                    status=ClarificationPlanStatus.QUESTIONS_REQUIRED,
                    round_number=current_round,
                    rationale="Resolving historical circular applicability requires the exact transaction date.",
                )

        # 5. Check Regulatory Coverage Unresolved
        if assessment_result.status == AssessmentStatus.REGULATORY_COVERAGE_UNRESOLVED:
            if "organisation" not in case_state.facts and "organisation" not in case_state.declined_fields:
                spec = CANONICAL_QUESTIONS["organisation"]
                q_text = spec.get(language, spec["en"])
                q = ClarificationQuestion(
                    field="organisation",
                    question=q_text,
                    reason="Authoritative regulatory jurisdiction requires confirming the identity of the registered broker/depository.",
                    priority=QuestionPriority.HIGH,
                    expected_answer_type="STRING",
                    acceptable_evidence_types=spec["acceptable_evidence_types"],
                    multilingual_text={"en": spec["en"], "hi": spec["hi"], "hinglish": spec["hinglish"]},
                )
                return ClarificationPlan(
                    plan_id=plan_id,
                    case_id=case_state.case_id,
                    case_version=case_state.version,
                    questions=[q],
                    status=ClarificationPlanStatus.QUESTIONS_REQUIRED,
                    round_number=current_round,
                    rationale="Intermediary identity is needed to establish regulatory jurisdiction.",
                )
            else:
                return ClarificationPlan(
                    plan_id=plan_id,
                    case_id=case_state.case_id,
                    case_version=case_state.version,
                    questions=[],
                    status=ClarificationPlanStatus.REGULATORY_COVERAGE_UNRESOLVED,
                    round_number=current_round,
                    rationale="Intermediary is known but lacks statutory depository coverage; cannot be resolved by user questions.",
                )

        # 6. Evaluate Missing Evidentiary Fields
        candidate_questions: list[ClarificationQuestion] = []
        missing_fields = list(assessment_result.missing_information)
        for req in assessment_result.evidence_requirements:
            if req.status == EvidenceRequirementStatus.MISSING and req.field_name not in missing_fields:
                missing_fields.append(req.field_name)

        # Sort missing fields by Information Gain Priority:
        # transaction_type > charged_amount > transaction_date > is_bsda > organisation > contract_note
        priority_order = ["transaction_type", "charged_amount", "transaction_date", "is_bsda", "organisation", "contract_note"]
        sorted_fields = sorted(
            missing_fields,
            key=lambda f: priority_order.index(f) if f in priority_order else 99,
        )

        for field in sorted_fields:
            # Skip if already known in confirmed facts
            if field in case_state.facts and case_state.facts[field] is not None:
                continue
            # Skip if explicitly declined by citizen
            if field in case_state.declined_fields:
                continue

            if field in CANONICAL_QUESTIONS:
                spec = CANONICAL_QUESTIONS[field]
                q_text = spec.get(language, spec["en"])
                q = ClarificationQuestion(
                    field=field,
                    question=q_text,
                    reason=spec["reason"],
                    priority=spec["priority"],
                    expected_answer_type=spec["expected_answer_type"],
                    acceptable_values=spec.get("acceptable_values"),
                    acceptable_evidence_types=spec["acceptable_evidence_types"],
                    multilingual_text={"en": spec["en"], "hi": spec["hi"], "hinglish": spec["hinglish"]},
                )
                candidate_questions.append(q)
            else:
                # Generic fallback for uncatalogued missing field
                en_q = f"Please provide the {field.replace('_', ' ')} related to this grievance."
                hi_q = f"कृपया इस शिकायत से संबंधित {field.replace('_', ' ')} प्रदान करें।"
                hinglish_q = f"Please {field.replace('_', ' ')} provide karein."
                q_text = hi_q if language == "hi" else (hinglish_q if language == "hinglish" else en_q)
                candidate_questions.append(
                    ClarificationQuestion(
                        field=field,
                        question=q_text,
                        reason=f"Field '{field}' is required to evaluate applicable statutory provisions.",
                        priority=QuestionPriority.MEDIUM,
                        expected_answer_type="STRING",
                        multilingual_text={"en": en_q, "hi": hi_q, "hinglish": hinglish_q},
                    )
                )

            if len(candidate_questions) >= self.max_questions_per_turn:
                break

        if candidate_questions:
            return ClarificationPlan(
                plan_id=plan_id,
                case_id=case_state.case_id,
                case_version=case_state.version,
                questions=candidate_questions,
                status=ClarificationPlanStatus.QUESTIONS_REQUIRED,
                round_number=current_round,
                rationale=f"Requesting {len(candidate_questions)} prioritized evidentiary item(s) to evaluate statutory compliance.",
            )

        # If missing fields exist but all were declined:
        if any(f in case_state.declined_fields for f in missing_fields):
            return ClarificationPlan(
                plan_id=plan_id,
                case_id=case_state.case_id,
                case_version=case_state.version,
                questions=[],
                status=ClarificationPlanStatus.USER_DECLINED,
                round_number=current_round,
                rationale="Required evidentiary fields were declined by user; proceeding with final insufficient determination.",
            )

        return ClarificationPlan(
            plan_id=plan_id,
            case_id=case_state.case_id,
            case_version=case_state.version,
            questions=[],
            status=ClarificationPlanStatus.INSUFFICIENT_EVIDENCE,
            round_number=current_round,
            rationale="No further clarification questions can be planned with available rules.",
        )
