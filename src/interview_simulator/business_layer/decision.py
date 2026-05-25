"""Map 0–5 structured scores + session counters to FSM driver events (README Part 2 ②)."""

from __future__ import annotations

from interview_simulator.business_layer.interview_fsm import InterviewEvent
from interview_simulator.business_layer.schemas import EvaluationPolicy, RoundScores
from interview_simulator.business_layer.score_weighting import weighted_score


def is_critical_fail(scores: RoundScores, policy: EvaluationPolicy | None = None) -> bool:
    """0–1 band on every axis."""

    _ = policy
    return (
        scores.technical_depth <= 1
        and scores.clarity <= 1
        and scores.relevance <= 1
    )


def is_satisfactory(scores: RoundScores, policy: EvaluationPolicy | None = None) -> bool:
    """4–5 band: weighted score close to correct."""

    policy = policy or EvaluationPolicy()
    if is_critical_fail(scores, policy):
        return False
    return weighted_score(scores) >= policy.satisfactory_weighted_min


def is_partial_answer(scores: RoundScores, policy: EvaluationPolicy | None = None) -> bool:
    """2–3 band: partial → follow-up when budget remains."""

    policy = policy or EvaluationPolicy()
    if is_critical_fail(scores, policy) or is_satisfactory(scores, policy):
        return False
    w = weighted_score(scores)
    return policy.partial_weighted_min <= w < policy.satisfactory_weighted_min


def is_weak_answer(scores: RoundScores, policy: EvaluationPolicy | None = None) -> bool:
    return is_partial_answer(scores, policy)


def is_severe_off_topic(scores: RoundScores, policy: EvaluationPolicy | None = None) -> bool:
    _ = policy
    return scores.relevance <= 1


def is_low_average_round(scores: RoundScores, policy: EvaluationPolicy | None = None) -> bool:
    """Cumulative early-end: weighted score <= low_avg_max (default 1.5)."""

    policy = policy or EvaluationPolicy()
    return weighted_score(scores) <= policy.low_avg_max + 1e-9


def round_average(scores: RoundScores) -> float:
    """Alias: weighted composite score used for decisions and UI."""

    return weighted_score(scores)


def decide_post_evaluation(
    scores: RoundScores,
    *,
    main_round_index: int,
    follow_ups_in_round: int,
    policy: EvaluationPolicy | None = None,
) -> InterviewEvent:
    policy = policy or EvaluationPolicy()
    partial = is_partial_answer(scores, policy)
    last_main_round = main_round_index >= policy.max_main_questions - 1

    if partial and follow_ups_in_round < policy.max_follow_ups_per_round:
        return InterviewEvent.EVAL_FOLLOW_UP

    return InterviewEvent.EVAL_FINALIZE if last_main_round else InterviewEvent.EVAL_NEXT_QUESTION


__all__ = [
    "decide_post_evaluation",
    "is_critical_fail",
    "is_low_average_round",
    "is_partial_answer",
    "is_satisfactory",
    "is_severe_off_topic",
    "is_weak_answer",
    "round_average",
]
