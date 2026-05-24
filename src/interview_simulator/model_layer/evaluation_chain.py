"""LLM scoring agent — evaluation_chain (Roadmap)."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from interview_simulator.model_layer.evaluation_prompts import (
    PRIOR_ANSWERS_BLOCK_EN,
    PRIOR_ANSWERS_BLOCK_ZH,
    PRIOR_BLOCK_EMPTY_EN,
    PRIOR_BLOCK_EMPTY_ZH,
    SCORER_SYSTEM,
    SCORER_USER,
)
from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from interview_simulator.model_layer.language import InterviewLanguage, scorer_language_rule
from interview_simulator.model_layer.score_alignment import PriorRound, calibrate_evaluation
from interview_simulator.model_layer.llm_factory import create_judge_llm
from interview_simulator.model_layer.observability import log_llm_event
from interview_simulator.model_layer.structured_compat import make_structured_chain


def _format_prior_block(prior_rounds: list[PriorRound], *, interview_language: InterviewLanguage) -> str:
    if not prior_rounds:
        return PRIOR_BLOCK_EMPTY_ZH if interview_language == "zh" else PRIOR_BLOCK_EMPTY_EN
    lines = []
    for i, r in enumerate(prior_rounds, start=1):
        lines.append(f"[{i}] Q: {r.question[:400]}\n    A: {r.answer[:400]}")
    block = "\n".join(lines)
    template = PRIOR_ANSWERS_BLOCK_ZH if interview_language == "zh" else PRIOR_ANSWERS_BLOCK_EN
    return template.format(prior_block=block)


class AnswerEvaluationAgent:
    """Independent scorer agent: structured 1–5 rubric + reasoning + key facts."""

    def __init__(self, llm=None) -> None:
        self._llm = llm or create_judge_llm(temperature=0.2)
        self._chain = make_structured_chain(
            ChatPromptTemplate.from_messages([("system", SCORER_SYSTEM), ("human", SCORER_USER)]),
            self._llm,
            AnswerEvaluationResult,
        )

    def _invoke(
        self,
        *,
        job_description: str,
        resume: str,
        question: str,
        answer: str,
        interview_language: InterviewLanguage,
        prior_rounds: list[PriorRound] | None,
    ) -> AnswerEvaluationResult:
        raw: AnswerEvaluationResult = self._chain.invoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "question": question.strip(),
                "answer": answer.strip(),
                "language_rule": scorer_language_rule(interview_language),
                "prior_answers_block": _format_prior_block(prior_rounds or [], interview_language=interview_language),
            }
        )
        return calibrate_evaluation(
            raw,
            question=question,
            answer=answer,
            prior_rounds=prior_rounds,
        )

    def score(
        self,
        *,
        job_description: str,
        resume: str,
        question: str,
        answer: str,
        interview_language: InterviewLanguage = "zh",
        prior_rounds: list[PriorRound] | None = None,
    ) -> AnswerEvaluationResult:
        log_llm_event(agent="scorer", operation="score", status="start")
        result = self._invoke(
            job_description=job_description,
            resume=resume,
            question=question,
            answer=answer,
            interview_language=interview_language,
            prior_rounds=prior_rounds,
        )
        log_llm_event(agent="scorer", operation="score", status="ok")
        return result

    async def ascore(
        self,
        *,
        job_description: str,
        resume: str,
        question: str,
        answer: str,
        interview_language: InterviewLanguage = "zh",
        prior_rounds: list[PriorRound] | None = None,
    ) -> AnswerEvaluationResult:
        log_llm_event(agent="scorer", operation="ascore", status="start")
        raw: AnswerEvaluationResult = await self._chain.ainvoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "question": question.strip(),
                "answer": answer.strip(),
                "language_rule": scorer_language_rule(interview_language),
                "prior_answers_block": _format_prior_block(prior_rounds or [], interview_language=interview_language),
            }
        )
        result = calibrate_evaluation(
            raw,
            question=question,
            answer=answer,
            prior_rounds=prior_rounds,
        )
        log_llm_event(agent="scorer", operation="ascore", status="ok")
        return result


__all__ = ["AnswerEvaluationAgent"]
