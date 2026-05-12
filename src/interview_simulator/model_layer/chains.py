"""LCEL-style chains: generate → self-critique → optional rewrite (README model layer)."""

from __future__ import annotations

import os
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from interview_simulator.model_layer.prompts import (
    CRITIQUE_SYSTEM,
    CRITIQUE_USER,
    GENERATION_SYSTEM,
    GENERATION_USER,
    REWRITE_SYSTEM,
    REWRITE_USER,
)
from interview_simulator.model_layer.schemas import (
    GeneratedQuestion,
    QuestionComposerResult,
    QuestionCritique,
)


def _default_llm(model: str | None = None, temperature: float = 0.4) -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it or load a .env file before invoking the composer."
        )
    return ChatOpenAI(
        model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=temperature,
        api_key=api_key,
    )


class InterviewQuestionComposer:
    """Generate a question, self-critique difficulty/relevance, rewrite once if needed."""

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> None:
        self._llm = llm or _default_llm(model=model, temperature=temperature)
        self._gen = ChatPromptTemplate.from_messages(
            [("system", GENERATION_SYSTEM), ("human", GENERATION_USER)]
        ) | self._llm.with_structured_output(GeneratedQuestion)
        self._crit = ChatPromptTemplate.from_messages(
            [("system", CRITIQUE_SYSTEM), ("human", CRITIQUE_USER)]
        ) | self._llm.with_structured_output(QuestionCritique)
        self._rewrite = ChatPromptTemplate.from_messages(
            [("system", REWRITE_SYSTEM), ("human", REWRITE_USER)]
        ) | self._llm.with_structured_output(GeneratedQuestion)

    def compose(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str = "technical depth",
        expected_depth: Literal["junior", "mid", "senior"] = "mid",
    ) -> QuestionComposerResult:
        """Run generate → critique; if inadequate, one rewrite pass."""
        initial = self._gen.invoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "dimension": dimension,
                "expected_depth": expected_depth,
            }
        )
        critique = self._crit.invoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "expected_depth": expected_depth,
                "question_text": initial.question_text,
            }
        )
        ok = critique.difficulty_adequate and critique.relevance_adequate
        if ok:
            return QuestionComposerResult(
                final_question=initial.question_text,
                expected_depth=initial.expected_depth,
                was_rewritten=False,
                critique=critique,
                initial_question=initial.question_text,
            )
        hint = critique.improvement_hint or critique.reasoning
        revised = self._rewrite.invoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "dimension": dimension,
                "expected_depth": expected_depth,
                "question_text": initial.question_text,
                "critique_reasoning": critique.reasoning,
                "improvement_hint": hint,
            }
        )
        return QuestionComposerResult(
            final_question=revised.question_text,
            expected_depth=revised.expected_depth,
            was_rewritten=True,
            critique=critique,
            initial_question=initial.question_text,
        )

    async def acompose(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str = "technical depth",
        expected_depth: Literal["junior", "mid", "senior"] = "mid",
    ) -> QuestionComposerResult:
        initial = await self._gen.ainvoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "dimension": dimension,
                "expected_depth": expected_depth,
            }
        )
        critique = await self._crit.ainvoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "expected_depth": expected_depth,
                "question_text": initial.question_text,
            }
        )
        ok = critique.difficulty_adequate and critique.relevance_adequate
        if ok:
            return QuestionComposerResult(
                final_question=initial.question_text,
                expected_depth=initial.expected_depth,
                was_rewritten=False,
                critique=critique,
                initial_question=initial.question_text,
            )
        hint = critique.improvement_hint or critique.reasoning
        revised = await self._rewrite.ainvoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "dimension": dimension,
                "expected_depth": expected_depth,
                "question_text": initial.question_text,
                "critique_reasoning": critique.reasoning,
                "improvement_hint": hint,
            }
        )
        return QuestionComposerResult(
            final_question=revised.question_text,
            expected_depth=revised.expected_depth,
            was_rewritten=True,
            critique=critique,
            initial_question=initial.question_text,
        )


def load_dotenv_if_present() -> None:
    """Optional: load .env from cwd so OPENAI_API_KEY works in local dev."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


__all__ = ["InterviewQuestionComposer", "load_dotenv_if_present"]
