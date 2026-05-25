"""Business-layer types for scoring decisions and memory (README Part 2 ②③)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RoundScores(BaseModel):
    """Structured per-turn scores (0–5 per axis)."""

    technical_depth: int = Field(..., ge=0, le=5, description="Technical correctness / depth.")
    clarity: int = Field(..., ge=0, le=5, description="How clear and structured the answer is.")
    relevance: int = Field(..., ge=0, le=5, description="Alignment with the stated question.")


class EvaluationPolicy(BaseModel):
    """Thresholds for mapping 0–5 scores + session counters to FSM events."""

    satisfactory_weighted_min: float = Field(
        4.0,
        ge=0.0,
        le=5.0,
        description="Weighted score (0.3/0.2/0.5) >= this → next main question.",
    )
    partial_weighted_min: float = Field(
        2.0,
        ge=0.0,
        le=5.0,
        description="Weighted score in [partial_weighted_min, satisfactory_weighted_min) → follow-up.",
    )
    duplicate_warnings_to_end: int = Field(
        2,
        ge=1,
        description="End interview after this many duplicate/off-topic answer warnings.",
    )
    low_avg_rounds_to_end: int = Field(
        2,
        ge=1,
        description="End interview after this many scored rounds with weighted score <= low_avg_max.",
    )
    low_avg_max: float = Field(
        1.5,
        ge=0.0,
        le=5.0,
        description="0.3×技术 + 0.2×清晰 + 0.5×相关 <= this value counts as a low round.",
    )
    max_follow_ups_per_round: int = Field(2, ge=0, description="Follow-ups allowed after each main question.")
    max_main_questions: int = Field(5, ge=1, description="Cap on main question rounds before forced finalize.")


class TurnRecord(BaseModel):
    """One QA slice for tail replay and optional fact extraction."""

    role: Literal["interviewer", "candidate"]
    text: str = Field(..., description="Utterance text (may be truncated upstream).")


class CompletedRoundDTO(BaseModel):
    """One completed Q/A turn with scores (shared by API, service, and report agent)."""

    main_round_index: int
    follow_ups_in_round_at_submit: int
    question: str
    answer: str
    scores: RoundScores


__all__ = ["CompletedRoundDTO", "EvaluationPolicy", "RoundScores", "TurnRecord"]
