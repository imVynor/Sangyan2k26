"""Clarification Dialogue and Question Quality Evaluator for SANGYAN (Phase 7A).

Epistemic foundation:
- Measures clarification precision and recall against materially relevant uncertainties.
- Strictly penalizes unnecessary questions and repetitious queries.
"""

import logging
from typing import Any, Sequence

from ai.evaluation.corpus.models import EvaluationCase, StageEvaluationResult

logger = logging.getLogger("sangyan.evaluation.clarification")


class ClarificationEvaluator:
    """Evaluates clarification questions generated for incomplete grievance cases."""

    def evaluate(
        self,
        case: EvaluationCase,
        actual_questions: Sequence[str] | Sequence[dict[str, Any]],
    ) -> StageEvaluationResult:
        if not case.expected_clarifications:
            # If no clarifications expected, any asked question is unnecessary
            if actual_questions:
                return StageEvaluationResult(
                    stage_name="CLARIFICATION",
                    passed=False,
                    score=0.0,
                    details={
                        "expected_clarifications": 0,
                        "actual_questions_count": len(actual_questions),
                        "unnecessary_questions_asked": len(actual_questions),
                    },
                    discrepancies=[f"Unnecessary clarification requested when facts were complete: {actual_questions}"],
                    failure_class="UNNECESSARY_CLARIFICATION",
                )
            return StageEvaluationResult(
                stage_name="CLARIFICATION",
                passed=True,
                score=1.0,
                details={"skipped": True, "reason": "No clarifications expected and none asked"},
            )

        exp = case.expected_clarifications
        discrepancies: list[str] = []

        # Extract text from questions
        question_texts: list[str] = []
        for q in actual_questions:
            if isinstance(q, str):
                question_texts.append(q)
            elif isinstance(q, dict):
                text = q.get("question") or q.get("prompt") or q.get("text") or str(q)
                question_texts.append(text)

        # 1. Evaluate required clarifications recall
        matched_required = 0
        all_acceptable = exp.required_clarifications + exp.acceptable_clarifications
        for req in exp.required_clarifications:
            req_lower = req.lower()
            hit = any(
                req_lower in q.lower() or any(w in q.lower() for w in req_lower.split() if len(w) > 4)
                for q in question_texts
            )
            if hit:
                matched_required += 1
            else:
                discrepancies.append(f"Missing required clarification question: '{req}'")

        req_recall = (
            matched_required / len(exp.required_clarifications)
            if exp.required_clarifications
            else 1.0
        )

        # 2. Evaluate unnecessary questions
        unnecessary_hits = 0
        for unnec in exp.unnecessary_questions:
            unnec_lower = unnec.lower()
            hit = any(
                unnec_lower in q.lower() or any(w in q.lower() for w in unnec_lower.split() if len(w) > 4)
                for q in question_texts
            )
            if hit:
                unnecessary_hits += 1
                discrepancies.append(f"UNNECESSARY QUESTION ASKED: '{unnec}' was asked unnecessarily")

        unnecessary_rate = (
            unnecessary_hits / len(question_texts)
            if question_texts
            else 0.0
        )

        # 3. Precision: fraction of asked questions that match an acceptable target
        relevant_asked = 0
        for q in question_texts:
            q_lower = q.lower()
            if any(
                acc.lower() in q_lower or any(w in q_lower for w in acc.lower().split() if len(w) > 4)
                for acc in all_acceptable
            ):
                relevant_asked += 1

        precision = (relevant_asked / len(question_texts)) if question_texts else (1.0 if not exp.required_clarifications else 0.0)

        passed = (req_recall >= 0.8) and (unnecessary_hits == 0)
        score = max(0.0, (0.5 * req_recall) + (0.5 * precision) - (0.3 * unnecessary_rate))

        return StageEvaluationResult(
            stage_name="CLARIFICATION",
            passed=passed,
            score=score,
            details={
                "required_count": len(exp.required_clarifications),
                "matched_required": matched_required,
                "recall": req_recall,
                "precision": precision,
                "unnecessary_hits": unnecessary_hits,
                "unnecessary_rate": unnecessary_rate,
                "questions_asked": question_texts,
            },
            discrepancies=discrepancies,
            failure_class="UNNECESSARY_QUESTION" if unnecessary_hits > 0 else ("CLARIFICATION_RECALL_MISS" if req_recall < 0.8 else None),
        )
