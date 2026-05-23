"""LLM scoring agent — evaluation_chain (Roadmap)."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from interview_simulator.model_layer.evaluation_prompts import SCORER_SYSTEM, SCORER_USER
from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from interview_simulator.model_layer.language import InterviewLanguage, scorer_language_rule
from interview_simulator.model_layer.llm_factory import create_judge_llm
from interview_simulator.model_layer.observability import log_llm_event
from interview_simulator.model_layer.structured_compat import make_structured_chain


class AnswerEvaluationAgent:
    """Independent scorer agent: structured 1–5 rubric + reasoning + key facts."""

    def __init__(self, llm=None) -> None:
        self._llm = llm or create_judge_llm(temperature=0.2)
        self._chain = make_structured_chain(
            ChatPromptTemplate.from_messages([("system", SCORER_SYSTEM), ("human", SCORER_USER)]),
            self._llm,
            AnswerEvaluationResult,
        )

    def score(
        self,
        *,
        job_description: str,
        resume: str,
        question: str,
        answer: str,
        interview_language: InterviewLanguage = "zh",
    ) -> AnswerEvaluationResult:
        log_llm_event(agent="scorer", operation="score", status="start")
        result: AnswerEvaluationResult = self._chain.invoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "question": question.strip(),
                "answer": answer.strip(),
                "language_rule": scorer_language_rule(interview_language),
            }
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
    ) -> AnswerEvaluationResult:
        log_llm_event(agent="scorer", operation="ascore", status="start")
        result: AnswerEvaluationResult = await self._chain.ainvoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "question": question.strip(),
                "answer": answer.strip(),
                "language_rule": scorer_language_rule(interview_language),
            }
        )
        log_llm_event(agent="scorer", operation="ascore", status="ok")
        return result


__all__ = ["AnswerEvaluationAgent"]
