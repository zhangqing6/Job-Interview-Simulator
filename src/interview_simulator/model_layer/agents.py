"""Multi-agent orchestration: interviewer + scorer + reporter."""

from __future__ import annotations

import os
from typing import Any, Literal, Protocol

from interview_simulator.business_layer.schemas import RoundScores
from interview_simulator.model_layer.language import InterviewLanguage
from interview_simulator.model_layer.chains import InterviewQuestionComposer
from interview_simulator.model_layer.evaluation_chain import AnswerEvaluationAgent
from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from interview_simulator.model_layer.score_alignment import PriorRound, heuristic_evaluate
from interview_simulator.model_layer.llm_factory import (
    is_llm_report_enabled,
    is_llm_scoring_enabled,
    llm_enabled,
)
from interview_simulator.model_layer.report_chain import InterviewReportAgent
from interview_simulator.model_layer.report_schemas import InterviewLLMReport
from interview_simulator.model_layer.schemas import QuestionComposerResult


class ScorerLike(Protocol):
    async def ascore(
        self,
        *,
        job_description: str,
        resume: str,
        question: str,
        answer: str,
        interview_language: InterviewLanguage = "zh",
        prior_rounds: list[PriorRound] | None = None,
    ) -> AnswerEvaluationResult: ...


class ReporterLike(Protocol):
    async def agenerate(
        self,
        *,
        job_description: str,
        resume: str,
        memory_context: str,
        rounds: list[Any],
        interview_language: InterviewLanguage = "zh",
    ) -> InterviewLLMReport: ...


class HeuristicScorer:
    """Question-aligned 1–5 rubric when LLM scoring is disabled (tests / no API key)."""

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
        _ = (job_description, resume)
        return heuristic_evaluate(
            question=question,
            answer=answer,
            prior_rounds=prior_rounds,
            interview_language=interview_language,
        )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class InterviewAgentOrchestrator:
    """Facade wiring three agents; HTTP layer talks to this instead of a single chain."""

    def __init__(
        self,
        *,
        interviewer: InterviewQuestionComposer | Any | None = None,
        scorer: ScorerLike | None = None,
        reporter: ReporterLike | None = None,
        use_llm_scoring: bool | None = None,
        use_llm_report: bool | None = None,
    ) -> None:
        llm_on = llm_enabled()
        score_on = use_llm_scoring if use_llm_scoring is not None else is_llm_scoring_enabled()
        report_on = use_llm_report if use_llm_report is not None else is_llm_report_enabled()

        self.interviewer = interviewer or InterviewQuestionComposer()
        if scorer is not None:
            self.scorer = scorer
        elif score_on and llm_on:
            self.scorer = AnswerEvaluationAgent()
        else:
            self.scorer = HeuristicScorer()

        if reporter is not None:
            self.reporter = reporter
        elif report_on and llm_on:
            self.reporter = InterviewReportAgent()
        else:
            self.reporter = None

        # Custom agents (e.g. test fakes) count as LLM paths even without API key.
        self.use_llm_scoring = not isinstance(self.scorer, HeuristicScorer)
        self.use_llm_report = self.reporter is not None

    async def compose_question(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str,
        expected_depth: Literal["junior", "mid", "senior"],
        prompt_strategy: Literal["zero_shot", "few_shot", "cot"] = "cot",
        interview_language: InterviewLanguage = "zh",
    ) -> QuestionComposerResult:
        if hasattr(self.interviewer, "acompose"):
            return await self.interviewer.acompose(
                job_description,
                resume,
                dimension=dimension,
                expected_depth=expected_depth,
                prompt_strategy=prompt_strategy,
                interview_language=interview_language,
            )
        import asyncio

        return await asyncio.to_thread(
            self.interviewer.compose,
            job_description,
            resume,
            dimension=dimension,
            expected_depth=expected_depth,
            prompt_strategy=prompt_strategy,
            interview_language=interview_language,
        )

    async def score_answer(
        self,
        *,
        job_description: str,
        resume: str,
        question: str,
        answer: str,
        interview_language: InterviewLanguage = "zh",
        prior_rounds: list[PriorRound] | None = None,
    ) -> AnswerEvaluationResult:
        return await self.scorer.ascore(
            job_description=job_description,
            resume=resume,
            question=question,
            answer=answer,
            interview_language=interview_language,
            prior_rounds=prior_rounds,
        )

    async def build_report(
        self,
        *,
        job_description: str,
        resume: str,
        memory_context: str,
        rounds: list[Any],
        interview_language: InterviewLanguage = "zh",
    ) -> InterviewLLMReport | None:
        if self.reporter is None:
            return None
        return await self.reporter.agenerate(
            job_description=job_description,
            resume=resume,
            memory_context=memory_context,
            rounds=rounds,
            interview_language=interview_language,
        )


__all__ = [
    "HeuristicScorer",
    "InterviewAgentOrchestrator",
    "ReporterLike",
    "ScorerLike",
]
