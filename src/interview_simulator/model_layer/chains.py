"""LCEL-style chains: generate → self-critique → optional rewrite (README model layer)."""

from __future__ import annotations

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate

from interview_simulator.model_layer.language import (
    InterviewLanguage,
    critique_language_rule,
    question_language_rule,
)
from interview_simulator.model_layer.llm_factory import create_chat_llm, use_question_critique
from interview_simulator.model_layer.structured_compat import make_structured_chain
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
        _gen_prompt = ChatPromptTemplate.from_messages(
            [("system", GENERATION_SYSTEM), ("human", GENERATION_USER)]
        )
        _inherit_depth = ("expected_depth",)
        self._gen_cot = make_structured_chain(
            _gen_prompt, self._llm, GeneratedQuestion, inherit_fields=_inherit_depth
        )
        self._gen_zero = make_structured_chain(
            ChatPromptTemplate.from_messages(
                [("system", ZERO_SHOT_GENERATION_SYSTEM), ("human", GENERATION_USER)]
            ),
            self._llm,
            GeneratedQuestion,
            inherit_fields=_inherit_depth,
        )
        self._gen_few = make_structured_chain(
            ChatPromptTemplate.from_messages(
                [("system", FEW_SHOT_GENERATION_PREFIX + "\n" + GENERATION_SYSTEM), ("human", GENERATION_USER)]
            ),
            self._llm,
            GeneratedQuestion,
            inherit_fields=_inherit_depth,
        )
        self._crit = make_structured_chain(
            ChatPromptTemplate.from_messages([("system", CRITIQUE_SYSTEM), ("human", CRITIQUE_USER)]),
            self._llm,
            QuestionCritique,
        )
        self._rewrite = make_structured_chain(
            ChatPromptTemplate.from_messages([("system", REWRITE_SYSTEM), ("human", REWRITE_USER)]),
            self._llm,
            GeneratedQuestion,
            inherit_fields=_inherit_depth,
        )

    def _gen_chain(self, prompt_strategy: PromptStrategy):
        if prompt_strategy == "zero_shot":
            return self._gen_zero
        if prompt_strategy == "few_shot":
            return self._gen_few
        return self._gen_cot

    @staticmethod
    def _skipped_critique() -> QuestionCritique:
        return QuestionCritique(
            difficulty_adequate=True,
            relevance_adequate=True,
            reasoning="single-pass compose (critique disabled)",
            improvement_hint=None,
        )

    def _from_initial(
        self,
        initial: GeneratedQuestion,
        *,
        prompt_strategy: PromptStrategy,
    ) -> QuestionComposerResult:
        return QuestionComposerResult(
            final_question=initial.question_text,
            expected_depth=initial.expected_depth,
            was_rewritten=False,
            critique=self._skipped_critique(),
            initial_question=initial.question_text,
            prompt_strategy=prompt_strategy,
        )

    def _payload(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str,
        expected_depth: Literal["junior", "mid", "senior"],
        interview_language: InterviewLanguage = "zh",
        for_critique: bool = False,
    ) -> dict:
        rule = critique_language_rule(interview_language) if for_critique else question_language_rule(
            interview_language
        )
        return {
            "job_description": job_description.strip(),
            "resume": resume.strip(),
            "dimension": dimension,
            "expected_depth": expected_depth,
            "language_rule": rule,
        }

    def compose(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str = "technical depth",
        expected_depth: Literal["junior", "mid", "senior"] = "mid",
        prompt_strategy: PromptStrategy = "cot",
        interview_language: InterviewLanguage = "zh",
    ) -> QuestionComposerResult:
        gen = self._gen_chain(prompt_strategy)
        base = self._payload(
            job_description,
            resume,
            dimension=dimension,
            expected_depth=expected_depth,
            interview_language=interview_language,
        )
        initial = gen.invoke(base)
        if prompt_strategy == "zero_shot" or not use_question_critique():
            return self._from_initial(initial, prompt_strategy=prompt_strategy)

        critique = self._crit.invoke(
            {
                **self._payload(
                    job_description,
                    resume,
                    dimension=dimension,
                    expected_depth=expected_depth,
                    interview_language=interview_language,
                    for_critique=True,
                ),
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
                **base,
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
        interview_language: InterviewLanguage = "zh",
    ) -> QuestionComposerResult:
        gen = self._gen_chain(prompt_strategy)
        base = self._payload(
            job_description,
            resume,
            dimension=dimension,
            expected_depth=expected_depth,
            interview_language=interview_language,
        )
        initial = await gen.ainvoke(base)
        if prompt_strategy == "zero_shot" or not use_question_critique():
            return self._from_initial(initial, prompt_strategy=prompt_strategy)

        critique = await self._crit.ainvoke(
            {
                **self._payload(
                    job_description,
                    resume,
                    dimension=dimension,
                    expected_depth=expected_depth,
                    interview_language=interview_language,
                    for_critique=True,
                ),
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
                **base,
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
