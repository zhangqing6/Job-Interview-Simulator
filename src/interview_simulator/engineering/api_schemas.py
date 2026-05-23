"""HTTP API request/response models (README: FastAPI + Pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from interview_simulator.business_layer.schemas import (
    CompletedRoundDTO,
    EvaluationPolicy,
    RoundScores,
)


PromptStrategy = Literal["zero_shot", "few_shot", "cot"]
InterviewLanguage = Literal["zh", "en"]


class InterviewStartRequest(BaseModel):
    job_description: str = Field(..., min_length=1)
    resume: str = Field(..., min_length=1)
    interview_dimension: str = Field(
        "technical depth",
        description="Focus hint passed to the question composer.",
    )
    expected_depth: Literal["junior", "mid", "senior"] = "mid"
    evaluation_policy: EvaluationPolicy | None = Field(
        default=None,
        description="If omitted, server defaults are used.",
    )
    prompt_strategy: PromptStrategy = Field(
        "cot",
        description="Prompt experiment: zero_shot | few_shot | cot (CoT + self-critique).",
    )
    stream: bool = Field(
        False,
        description="If true, use POST /interview/start/stream for SSE token stream.",
    )
    interview_language: InterviewLanguage = Field(
        "zh",
        description="Language for questions, follow-ups, scoring reasoning, and report text (zh | en).",
    )


class InterviewStartResponse(BaseModel):
    session_id: str
    state: str
    prompt_lane: str
    current_question: str
    prompt_strategy: PromptStrategy = "cot"
    interview_language: InterviewLanguage = "zh"
    scores_source: str | None = None


class InterviewAskRequest(BaseModel):
    session_id: str
    answer: str = Field(..., min_length=1)
    scores: RoundScores | None = Field(
        default=None,
        description="Optional client scores (1–5). If omitted, LLM scorer runs when enabled.",
    )
    use_llm_scoring: bool | None = Field(
        default=None,
        description="Override USE_LLM_SCORING for this request.",
    )


class InterviewAskResponse(BaseModel):
    session_id: str
    state: str
    prompt_lane: str
    finalized: bool = False
    current_question: str | None = None
    message: str | None = Field(
        default=None,
        description="Short UX hint, e.g. interview ended or next prompt lane.",
    )
    scores: RoundScores | None = None
    scores_source: Literal["client", "llm", "heuristic"] | None = None
    evaluation_reasoning: str | None = None


class InterviewStatusResponse(BaseModel):
    session_id: str
    state: str
    prompt_lane: str
    context: dict
    current_question: str
    memory_context_excerpt: str
    report_ready: bool = False


class InterviewReportResponse(BaseModel):
    session_id: str
    state: str
    rounds: list[CompletedRoundDTO]
    closing_summary: str
    overall_assessment: str | None = None
    strengths: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    recommended_study_topics: list[str] = Field(default_factory=list)
    report_source: Literal["llm", "heuristic"] = "heuristic"
    report_pending: bool = False


__all__ = [
    "CompletedRoundDTO",
    "InterviewLanguage",
    "InterviewAskRequest",
    "InterviewAskResponse",
    "InterviewReportResponse",
    "InterviewStartRequest",
    "InterviewStartResponse",
    "InterviewStatusResponse",
    "PromptStrategy",
]
