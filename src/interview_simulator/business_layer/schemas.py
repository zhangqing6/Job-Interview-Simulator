"""Business-layer types for scoring decisions and memory (README Part 2 ②③)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RoundScores(BaseModel):
    """Structured per-turn scores (1–5), aligned with README multi-axis rubric."""

    technical_depth: int = Field(..., ge=1, le=5, description="Technical correctness / depth.")
    clarity: int = Field(..., ge=1, le=5, description="How clear and structured the answer is.")
    relevance: int = Field(..., ge=1, le=5, description="Alignment with the stated question.")


class EvaluationPolicy(BaseModel):
    """Thresholds for mapping scores + session counters to FSM events."""

    low_score_threshold: float = Field(
        3.0,
        ge=1.0,
        le=5.0,
        description="Strictly below this average (1–5) counts as a weak answer.",
    )
    min_score_floor: int = Field(
        2,
        ge=1,
        le=5,
        description="Any axis at or below this value counts as weak even if the average is higher.",
    )
    severe_relevance_max: int = Field(
        2,
        ge=1,
        le=5,
        description="Relevance at or below this value is treated as severe off-topic → change topic.",
    )
    max_follow_ups_per_round: int = Field(2, ge=0, description="Follow-ups allowed after each main question.")
    max_main_questions: int = Field(5, ge=1, description="Cap on main question rounds before forced finalize.")
    consecutive_weak_to_end: int = Field(
        2,
        ge=1,
        description="End interview after this many consecutive weak main rounds (README: 连续多轮低分).",
    )


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
