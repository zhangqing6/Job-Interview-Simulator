"""Test doubles for multi-agent LLM paths (no OpenAI)."""

from __future__ import annotations

from typing import Any, Literal

from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from interview_simulator.model_layer.score_alignment import PriorRound, calibrate_evaluation
from interview_simulator.model_layer.report_schemas import InterviewLLMReport
from interview_simulator.model_layer.schemas import QuestionComposerResult, QuestionCritique


class FakeComposer:
    def __init__(self) -> None:
        self._n = 0

    def compose(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str,
        expected_depth: Literal["junior", "mid", "senior"],
        prompt_strategy: Literal["zero_shot", "few_shot", "cot"] = "cot",
        **_: Any,
    ) -> QuestionComposerResult:
        self._n += 1
        q = f"Q{self._n}: ({expected_depth}) {dimension[:40]}"
        crit = QuestionCritique(
            difficulty_adequate=True,
            relevance_adequate=True,
            reasoning="stub",
            improvement_hint=None,
        )
        return QuestionComposerResult(
            final_question=q,
            expected_depth=expected_depth,
            was_rewritten=False,
            critique=crit,
            initial_question=q,
            prompt_strategy=prompt_strategy,
        )

    async def acompose(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str,
        expected_depth: Literal["junior", "mid", "senior"],
        prompt_strategy: Literal["zero_shot", "few_shot", "cot"] = "cot",
        **_: Any,
    ) -> QuestionComposerResult:
        return self.compose(
            job_description,
            resume,
            dimension=dimension,
            expected_depth=expected_depth,
            prompt_strategy=prompt_strategy,
        )


class FakeScorer:
    async def ascore(
        self,
        *,
        job_description: str,
        resume: str,
        question: str,
        answer: str,
        prior_rounds: list[PriorRound] | None = None,
        **_: Any,
    ) -> AnswerEvaluationResult:
        _ = (job_description, resume)
        if answer.rstrip().endswith("vague"):
            return AnswerEvaluationResult(
                technical_depth=2,
                clarity=3,
                relevance=4,
                reasoning="Fake weak-but-on-topic answer (test marker).",
                key_facts=[],
            )
        depth = 5 if len(answer) > 20 else 2
        raw = AnswerEvaluationResult(
            technical_depth=depth,
            clarity=4,
            relevance=4,
            reasoning="Fake LLM scorer: longer answers score higher on depth.",
            key_facts=["Candidate mentioned concrete implementation details"],
        )
        return calibrate_evaluation(
            raw,
            question=question,
            answer=answer,
            prior_rounds=prior_rounds,
        )


class FakeReporter:
    async def agenerate(
        self,
        *,
        job_description: str,
        resume: str,
        memory_context: str,
        rounds: list[Any],
        **_: Any,
    ) -> InterviewLLMReport:
        _ = (job_description, resume, memory_context)
        n = len(rounds)
        return InterviewLLMReport(
            overall_assessment=f"Completed {n} round(s) with generally solid technical communication.",
            strengths=["Structured answers", "Relevant stack experience"],
            improvement_suggestions=[
                "Add quantitative metrics when discussing system design",
                "Practice concise trade-off summaries",
            ],
            recommended_study_topics=["Distributed tracing", "Load testing methodology"],
            closing_summary="Recommend proceeding to the next onsite stage with a system design deep-dive.",
        )
