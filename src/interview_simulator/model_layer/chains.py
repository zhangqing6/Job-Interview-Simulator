"""LCEL-style chains: generate → self-critique → optional rewrite (README model layer)."""

from __future__ import annotations

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate

from interview_simulator.model_layer.llm_factory import create_chat_llm
from interview_simulator.model_layer.prompt_strategy import (
    FEW_SHOT_GENERATION_PREFIX,
    PromptStrategy,
    ZERO_SHOT_GENERATION_SYSTEM,
)
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


class InterviewQuestionComposer:
    """Interviewer agent: question generation with optional prompt strategy experiments."""

    def __init__(
        self,
        llm=None,
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> None:
        self._llm = llm or create_chat_llm(
            model=model,
            temperature=temperature,
            agent="interviewer",
            operation="compose",
        )
        self._gen_cot = ChatPromptTemplate.from_messages(
            [("system", GENERATION_SYSTEM), ("human", GENERATION_USER)]
        ) | self._llm.with_structured_output(GeneratedQuestion)
        self._gen_zero = ChatPromptTemplate.from_messages(
            [("system", ZERO_SHOT_GENERATION_SYSTEM), ("human", GENERATION_USER)]
        ) | self._llm.with_structured_output(GeneratedQuestion)
        self._gen_few = ChatPromptTemplate.from_messages(
            [("system", FEW_SHOT_GENERATION_PREFIX + "\n" + GENERATION_SYSTEM), ("human", GENERATION_USER)]
        ) | self._llm.with_structured_output(GeneratedQuestion)
        self._crit = ChatPromptTemplate.from_messages(
            [("system", CRITIQUE_SYSTEM), ("human", CRITIQUE_USER)]
        ) | self._llm.with_structured_output(QuestionCritique)
        self._rewrite = ChatPromptTemplate.from_messages(
            [("system", REWRITE_SYSTEM), ("human", REWRITE_USER)]
        ) | self._llm.with_structured_output(GeneratedQuestion)

    def _gen_chain(self, prompt_strategy: PromptStrategy):
        if prompt_strategy == "zero_shot":
            return self._gen_zero
        if prompt_strategy == "few_shot":
            return self._gen_few
        return self._gen_cot

    def _payload(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str,
        expected_depth: Literal["junior", "mid", "senior"],
    ) -> dict:
        return {
            "job_description": job_description.strip(),
            "resume": resume.strip(),
            "dimension": dimension,
            "expected_depth": expected_depth,
        }

    def compose(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str = "technical depth",
        expected_depth: Literal["junior", "mid", "senior"] = "mid",
        prompt_strategy: PromptStrategy = "cot",
    ) -> QuestionComposerResult:
        if prompt_strategy == "zero_shot":
            initial = self._gen_zero.invoke(self._payload(job_description, resume, dimension=dimension, expected_depth=expected_depth))
            return QuestionComposerResult(
                final_question=initial.question_text,
                expected_depth=initial.expected_depth,
                was_rewritten=False,
                critique=QuestionCritique(
                    difficulty_adequate=True,
                    relevance_adequate=True,
                    reasoning="zero_shot: critique skipped",
                    improvement_hint=None,
                ),
                initial_question=initial.question_text,
                prompt_strategy=prompt_strategy,
            )

        gen = self._gen_chain(prompt_strategy)
        initial = gen.invoke(self._payload(job_description, resume, dimension=dimension, expected_depth=expected_depth))
        critique = self._crit.invoke(
            {
                **self._payload(job_description, resume, dimension=dimension, expected_depth=expected_depth),
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
                prompt_strategy=prompt_strategy,
            )
        hint = critique.improvement_hint or critique.reasoning
        revised = self._rewrite.invoke(
            {
                **self._payload(job_description, resume, dimension=dimension, expected_depth=expected_depth),
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
            prompt_strategy=prompt_strategy,
        )

    async def acompose(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str = "technical depth",
        expected_depth: Literal["junior", "mid", "senior"] = "mid",
        prompt_strategy: PromptStrategy = "cot",
    ) -> QuestionComposerResult:
        if prompt_strategy == "zero_shot":
            initial = await self._gen_zero.ainvoke(
                self._payload(job_description, resume, dimension=dimension, expected_depth=expected_depth)
            )
            return QuestionComposerResult(
                final_question=initial.question_text,
                expected_depth=initial.expected_depth,
                was_rewritten=False,
                critique=QuestionCritique(
                    difficulty_adequate=True,
                    relevance_adequate=True,
                    reasoning="zero_shot: critique skipped",
                    improvement_hint=None,
                ),
                initial_question=initial.question_text,
                prompt_strategy=prompt_strategy,
            )

        gen = self._gen_chain(prompt_strategy)
        initial = await gen.ainvoke(self._payload(job_description, resume, dimension=dimension, expected_depth=expected_depth))
        critique = await self._crit.ainvoke(
            {
                **self._payload(job_description, resume, dimension=dimension, expected_depth=expected_depth),
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
                prompt_strategy=prompt_strategy,
            )
        hint = critique.improvement_hint or critique.reasoning
        revised = await self._rewrite.ainvoke(
            {
                **self._payload(job_description, resume, dimension=dimension, expected_depth=expected_depth),
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
            prompt_strategy=prompt_strategy,
        )


def load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


__all__ = ["InterviewQuestionComposer", "load_dotenv_if_present"]
