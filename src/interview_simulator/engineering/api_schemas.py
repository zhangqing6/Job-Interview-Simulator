"""HTTP API request/response models (README: FastAPI + Pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from interview_simulator.business_layer.schemas import EvaluationPolicy, RoundScores


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


class InterviewStartResponse(BaseModel):
    session_id: str
    state: str
    prompt_lane: str
    current_question: str


class InterviewAskRequest(BaseModel):
    session_id: str
    answer: str = Field(..., min_length=1)
    scores: RoundScores | None = Field(
        default=None,
        description="Structured rubric scores (1–5). If omitted, neutral defaults are used until an LLM scorer is wired.",
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


class InterviewStatusResponse(BaseModel):
    session_id: str
    state: str
    prompt_lane: str
    context: dict
    current_question: str
    memory_context_excerpt: str


class CompletedRoundDTO(BaseModel):
    main_round_index: int
    follow_ups_in_round_at_submit: int
    question: str
    answer: str
    scores: RoundScores


class InterviewReportResponse(BaseModel):
    session_id: str
    state: str
    rounds: list[CompletedRoundDTO]
    closing_summary: str


__all__ = [
    "CompletedRoundDTO",
    "InterviewAskRequest",
    "InterviewAskResponse",
    "InterviewReportResponse",
    "InterviewStartRequest",
    "InterviewStartResponse",
    "InterviewStatusResponse",
]
