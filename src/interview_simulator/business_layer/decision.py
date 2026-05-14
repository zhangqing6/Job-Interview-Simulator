"""Map structured scores + session counters to FSM driver events (README Part 2 ②)."""

from __future__ import annotations

from interview_simulator.business_layer.interview_fsm import InterviewEvent
from interview_simulator.business_layer.schemas import EvaluationPolicy, RoundScores


def _average(scores: RoundScores) -> float:
    return (scores.technical_depth + scores.clarity + scores.relevance) / 3.0


def is_weak_answer(scores: RoundScores, policy: EvaluationPolicy) -> bool:
    if _average(scores) < policy.low_score_threshold:
        return True
    return min(scores.technical_depth, scores.clarity, scores.relevance) <= policy.min_score_floor


def is_severe_off_topic(scores: RoundScores, policy: EvaluationPolicy) -> bool:
    return scores.relevance <= policy.severe_relevance_max


def next_consecutive_weak_streak(
    *,
    previous: int,
    chosen_event: InterviewEvent,
    weak: bool,
) -> int:
    """How ``InterviewSessionContext.consecutive_weak_rounds`` should read after this decision."""

    if chosen_event is InterviewEvent.EVAL_FINALIZE:
        return previous
    if chosen_event is InterviewEvent.EVAL_FOLLOW_UP:
        return previous
    if chosen_event is InterviewEvent.EVAL_NEXT_QUESTION:
        return previous + 1 if weak else 0
    raise ValueError(f"Unexpected post-evaluation event: {chosen_event!r}")


def decide_post_evaluation(
    scores: RoundScores,
    *,
    main_round_index: int,
    follow_ups_in_round: int,
    consecutive_weak_rounds: int,
    policy: EvaluationPolicy | None = None,
) -> tuple[InterviewEvent, int]:
    """Return the FSM event to apply from ``EVALUATING``, plus the new weak-round streak.

    Rules (README):
    - Low scores → follow-up while budget remains.
    - Severe off-topic → skip follow-ups and move to the next main question (or finalize on last round).
    - Several consecutive weak main rounds → early finalize.
    - Last main question with a normal "next" decision → finalize instead of preparing another main question.
    """

    policy = policy or EvaluationPolicy()
    weak = is_weak_answer(scores, policy)
    off = is_severe_off_topic(scores, policy)

    last_main_round = main_round_index >= policy.max_main_questions - 1

    if off:
        base = InterviewEvent.EVAL_FINALIZE if last_main_round else InterviewEvent.EVAL_NEXT_QUESTION
    elif weak and follow_ups_in_round < policy.max_follow_ups_per_round:
        base = InterviewEvent.EVAL_FOLLOW_UP
    else:
        base = InterviewEvent.EVAL_NEXT_QUESTION if not last_main_round else InterviewEvent.EVAL_FINALIZE

    if base is InterviewEvent.EVAL_NEXT_QUESTION:
        hurts_streak = weak or off
        early_terminate = hurts_streak and (consecutive_weak_rounds + 1 >= policy.consecutive_weak_to_end)
        if early_terminate:
            base = InterviewEvent.EVAL_FINALIZE

    if base is InterviewEvent.EVAL_FINALIZE:
        return base, consecutive_weak_rounds

    new_streak = next_consecutive_weak_streak(
        previous=consecutive_weak_rounds,
        chosen_event=base,
        weak=weak or off,
    )
    return base, new_streak


__all__ = [
    "decide_post_evaluation",
    "is_severe_off_topic",
    "is_weak_answer",
    "next_consecutive_weak_streak",
]
