"""Question–answer alignment checks and score calibration (0–5 rubric)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from interview_simulator.business_layer.schemas import RoundScores
from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from interview_simulator.model_layer.language import InterviewLanguage
from interview_simulator.model_layer.score_rubric import RUBRIC_MAX, RUBRIC_MIN, normalize_evaluation_scores

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


@dataclass(frozen=True)
class PriorRound:
    question: str
    answer: str


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for raw in _TOKEN_RE.findall(text):
        t = raw.lower()
        if len(t) >= 2 or t.isascii():
            out.add(t)
        for ch in raw:
            if "\u4e00" <= ch <= "\u9fff":
                out.add(ch)
    return out


def lexical_overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def alignment_score(question: str, answer: str) -> float:
    tq, ta = _tokens(question), _tokens(answer)
    if not tq or not ta:
        return 0.0
    shared = tq & ta
    jaccard = len(shared) / len(tq | ta)
    coverage = len(shared) / len(tq)
    return max(jaccard, coverage)


def _clamp(n: int, lo: int = RUBRIC_MIN, hi: int = RUBRIC_MAX) -> int:
    return max(lo, min(hi, n))


def calibrate_evaluation(
    result: AnswerEvaluationResult,
    *,
    question: str,
    answer: str,
    prior_rounds: list[PriorRound] | None = None,
) -> AnswerEvaluationResult:
    """Cap inflated LLM scores when the answer does not address this question."""

    q, a = question.strip(), answer.strip()
    align = alignment_score(q, a)
    tech, clarity, rel = result.technical_depth, result.clarity, result.relevance
    notes: list[str] = []

    if align < 0.12:
        rel = min(rel, 1)
        tech = min(tech, 1)
        clarity = min(clarity, 2)
        notes.append("回答与题干关键词几乎无重叠，三轴已压至 0–1/2 档。")
    elif align < 0.22:
        rel = min(rel, 2)
        tech = min(tech, 3)
        notes.append("回答仅少量覆盖题干要点，分数限制在部分正确档。")

    if rel <= 1:
        tech = min(tech, 1)
        clarity = min(clarity, 2)

    reasoning = result.reasoning
    if notes:
        reasoning = f"{reasoning} [{' '.join(notes)}]"

    calibrated = AnswerEvaluationResult(
        technical_depth=_clamp(tech),
        clarity=_clamp(clarity),
        relevance=_clamp(rel),
        reasoning=reasoning,
        key_facts=list(result.key_facts),
    )
    data = normalize_evaluation_scores(calibrated.model_dump())
    return AnswerEvaluationResult(
        technical_depth=data["technical_depth"],
        clarity=data["clarity"],
        relevance=data["relevance"],
        reasoning=calibrated.reasoning,
        key_facts=calibrated.key_facts,
    )


def heuristic_evaluate(
    *,
    question: str,
    answer: str,
    prior_rounds: list[PriorRound] | None = None,
    interview_language: InterviewLanguage = "zh",
) -> AnswerEvaluationResult:
    """Deterministic 0–5 scoring from question–answer fit (no LLM)."""

    q, a = question.strip(), answer.strip()
    align = alignment_score(q, a)
    length = len(a)

    if align < 0.1 or length < 8:
        rel, tech = 1, 1
    elif align < 0.2:
        rel, tech = 2, 2
    elif align < 0.35:
        rel, tech = 3, 3
    elif align < 0.5:
        rel, tech = 4, 4
    else:
        rel, tech = 5, 5

    clarity = 2
    if length > 120:
        clarity = 4
    if length > 40 and ("\n" in a or "1." in a or "首先" in a or "First" in a.lower()):
        clarity = min(5, clarity + 1)

    base = AnswerEvaluationResult(
        technical_depth=_clamp(tech),
        clarity=_clamp(clarity),
        relevance=_clamp(rel),
        reasoning=(
            f"启发式评分：题答关键词重合度 {align:.0%}，按 0–5 量表（0–1 极差/2–3 部分/4–5 良好）给分。"
            if interview_language == "zh"
            else f"Heuristic score from Q–A overlap {align:.0%} on a 0–5 scale."
        ),
        key_facts=[],
    )
    return calibrate_evaluation(base, question=q, answer=a, prior_rounds=prior_rounds)


def is_duplicate_across_questions(
    question: str,
    answer: str,
    prior_rounds: list[PriorRound] | None,
    *,
    answer_similarity_min: float = 0.82,
    question_similarity_max: float = 0.45,
) -> bool:
    """True when answer closely copies a prior answer under a different question."""

    a = answer.strip()
    if not a or not prior_rounds:
        return False
    for prev in prior_rounds:
        if not prev.answer.strip():
            continue
        ans_sim = alignment_score(a, prev.answer)
        q_sim = alignment_score(question, prev.question)
        if ans_sim >= answer_similarity_min and q_sim < question_similarity_max:
            return True
    return False


__all__ = [
    "PriorRound",
    "alignment_score",
    "calibrate_evaluation",
    "heuristic_evaluate",
    "is_duplicate_across_questions",
    "lexical_overlap",
]
