"""LLM scoring agent — evaluation_chain (Roadmap)."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from interview_simulator.model_layer.evaluation_prompts import SCORER_SYSTEM, SCORER_USER
from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from interview_simulator.model_layer.llm_factory import create_chat_llm
from interview_simulator.model_layer.observability import log_llm_event


class AnswerEvaluationAgent:
    """Independent scorer agent: structured 1–5 rubric + reasoning + key facts."""

    def __init__(self, llm=None) -> None:
        self._llm = llm or create_chat_llm(agent="scorer", operation="score", temperature=0.2)
        self._chain = ChatPromptTemplate.from_messages(
            [("system", SCORER_SYSTEM), ("human", SCORER_USER)]
        ) | self._llm.with_structured_output(AnswerEvaluationResult)

    def score(
        self,
        *,
        job_description: str,
        resume: str,
        question: str,
        answer: str,
    ) -> AnswerEvaluationResult:
        log_llm_event(agent="scorer", operation="score", status="start")
        result: AnswerEvaluationResult = self._chain.invoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "question": question.strip(),
                "answer": answer.strip(),
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
    ) -> AnswerEvaluationResult:
        log_llm_event(agent="scorer", operation="ascore", status="start")
        result: AnswerEvaluationResult = await self._chain.ainvoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "question": question.strip(),
                "answer": answer.strip(),
            }
        )
        log_llm_event(agent="scorer", operation="ascore", status="ok")
        return result


__all__ = ["AnswerEvaluationAgent"]
