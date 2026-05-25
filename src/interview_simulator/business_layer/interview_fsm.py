"""Finite-state interview flow (README: initial → questioning → … → finalize).

Part 2 defines the FSM (①), scoring-driven transitions (``business_layer.decision``),
and compact memory (``business_layer.memory``).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class InterviewState(str, Enum):
    INITIAL = "initial"
    QUESTIONING = "questioning"
    WAITING_FOR_ANSWER = "waiting_for_answer"
    EVALUATING = "evaluating"
    FOLLOW_UP = "follow_up"
    NEXT_QUESTION = "next_question"
    FINALIZE = "finalize"


class InterviewEvent(str, Enum):
    """Driver events. Evaluation outcomes are represented as distinct events for a thin FSM."""

    START_SESSION = "start_session"
    QUESTION_PREPARED = "question_prepared"
    ANSWER_SUBMITTED = "answer_submitted"
    EVAL_FOLLOW_UP = "eval_follow_up"
    EVAL_NEXT_QUESTION = "eval_next_question"
    EVAL_FINALIZE = "eval_finalize"
    FOLLOW_UP_PREPARED = "follow_up_prepared"
    BEGIN_PREPARE_NEXT = "begin_prepare_next"


class InvalidStateTransition(ValueError):
    def __init__(self, state: InterviewState, event: InterviewEvent, message: str | None = None) -> None:
        self.state = state
        self.event = event
        detail = message or f"Event {event.value!r} is not valid in state {state.value!r}."
        super().__init__(detail)


# (from_state, event) -> to_state — single source of truth for Part 2a.
_TRANSITIONS: dict[tuple[InterviewState, InterviewEvent], InterviewState] = {
    (InterviewState.INITIAL, InterviewEvent.START_SESSION): InterviewState.QUESTIONING,
    (InterviewState.QUESTIONING, InterviewEvent.QUESTION_PREPARED): InterviewState.WAITING_FOR_ANSWER,
    (InterviewState.WAITING_FOR_ANSWER, InterviewEvent.ANSWER_SUBMITTED): InterviewState.EVALUATING,
    (InterviewState.EVALUATING, InterviewEvent.EVAL_FOLLOW_UP): InterviewState.FOLLOW_UP,
    (InterviewState.EVALUATING, InterviewEvent.EVAL_NEXT_QUESTION): InterviewState.NEXT_QUESTION,
    (InterviewState.EVALUATING, InterviewEvent.EVAL_FINALIZE): InterviewState.FINALIZE,
    (InterviewState.FOLLOW_UP, InterviewEvent.FOLLOW_UP_PREPARED): InterviewState.WAITING_FOR_ANSWER,
    (InterviewState.NEXT_QUESTION, InterviewEvent.BEGIN_PREPARE_NEXT): InterviewState.QUESTIONING,
}


def prompt_lane_for_state(state: InterviewState) -> str:
    """Which model/prompt lane is active (for wiring ``question_chain`` / ``follow_up_chain`` later)."""

    return {
        InterviewState.INITIAL: "bootstrap",
        InterviewState.QUESTIONING: "question_chain",
        InterviewState.WAITING_FOR_ANSWER: "none",
        InterviewState.EVALUATING: "evaluation_chain",
        InterviewState.FOLLOW_UP: "follow_up_chain",
        InterviewState.NEXT_QUESTION: "transition_next",
        InterviewState.FINALIZE: "report_chain",
    }[state]


class InterviewSessionContext(BaseModel):
    """Serializable snapshot suitable for ``GET /interview/status/{id}``."""

    state: InterviewState = InterviewState.INITIAL
    main_round_index: int = Field(0, ge=0, description="0-based index of the current main question round.")
    follow_ups_in_round: int = Field(0, ge=0, description="Follow-ups taken in the current main round.")
    duplicate_warning_count: int = Field(
        0,
        ge=0,
        description="Duplicate/off-topic answer warnings issued (two → early finalize).",
    )
    low_avg_round_count: int = Field(
        0,
        ge=0,
        description="Scored rounds with weighted score <= policy.low_avg_max (early finalize when >= threshold).",
    )
    turns_presented: int = Field(
        0,
        ge=0,
        description="How many prompts were shown to the candidate (main or follow-up).",
    )
    transition_steps: int = Field(0, ge=0, description="Successful FSM transitions applied.")


class InterviewStateMachine:
    """Explicit interview FSM; mutates a copy-on-write ``InterviewSessionContext``."""

    TERMINAL: ClassVar[frozenset[InterviewState]] = frozenset({InterviewState.FINALIZE})

    def __init__(self, context: InterviewSessionContext | None = None) -> None:
        self._ctx = context.model_copy(deep=True) if context else InterviewSessionContext()

    @property
    def context(self) -> InterviewSessionContext:
        return self._ctx

    def patch_context(self, **updates: Any) -> InterviewSessionContext:
        """Merge extra counters/metadata after a scoring decision without touching FSM legality."""

        self._ctx = self._ctx.model_copy(update=updates)
        return self._ctx

    def allowed_events(self) -> list[InterviewEvent]:
        if self._ctx.state in self.TERMINAL:
            return []
        return [e for (s, e) in _TRANSITIONS if s == self._ctx.state]

    def apply(self, event: InterviewEvent) -> InterviewSessionContext:
        if self._ctx.state in self.TERMINAL:
            raise InvalidStateTransition(self._ctx.state, event, "Interview already finalized.")
        key = (self._ctx.state, event)
        if key not in _TRANSITIONS:
            raise InvalidStateTransition(self._ctx.state, event)
        to_state = _TRANSITIONS[key]
        self._ctx = self._with_counters(self._ctx, event).model_copy(update={"state": to_state})
        return self._ctx

    @staticmethod
    def _with_counters(ctx: InterviewSessionContext, event: InterviewEvent) -> InterviewSessionContext:
        steps = ctx.transition_steps + 1
        turns = ctx.turns_presented
        round_idx = ctx.main_round_index
        follow_ups = ctx.follow_ups_in_round

        if event is InterviewEvent.QUESTION_PREPARED or event is InterviewEvent.FOLLOW_UP_PREPARED:
            turns += 1
        if event is InterviewEvent.EVAL_FOLLOW_UP:
            follow_ups += 1
        if event is InterviewEvent.EVAL_NEXT_QUESTION:
            follow_ups = 0
        if event is InterviewEvent.BEGIN_PREPARE_NEXT:
            round_idx += 1

        return ctx.model_copy(
            update={
                "transition_steps": steps,
                "turns_presented": turns,
                "main_round_index": round_idx,
                "follow_ups_in_round": follow_ups,
            }
        )


__all__ = [
    "InterviewEvent",
    "InterviewSessionContext",
    "InterviewState",
    "InterviewStateMachine",
    "InvalidStateTransition",
    "prompt_lane_for_state",
]
