"""Scoring → FSM event mapping (business layer Part 2 ②)."""

from interview_simulator.business_layer.decision import (
    decide_post_evaluation,
    is_severe_off_topic,
    is_weak_answer,
    next_consecutive_weak_streak,
)
from interview_simulator.business_layer.interview_fsm import InterviewEvent
from interview_simulator.business_layer.schemas import EvaluationPolicy, RoundScores


def _scores(tech: int, clarity: int, rel: int) -> RoundScores:
    return RoundScores(technical_depth=tech, clarity=clarity, relevance=rel)


def test_weak_triggers_follow_up_when_budget_remains() -> None:
    s = _scores(2, 3, 3)
    event, streak = decide_post_evaluation(
        s,
        main_round_index=0,
        follow_ups_in_round=0,
        consecutive_weak_rounds=0,
    )
    assert event is InterviewEvent.EVAL_FOLLOW_UP
    assert streak == 0


def test_severe_off_topic_skips_follow_up() -> None:
    s = _scores(4, 4, 1)
    assert is_severe_off_topic(s, EvaluationPolicy())
    event, streak = decide_post_evaluation(
        s,
        main_round_index=0,
        follow_ups_in_round=0,
        consecutive_weak_rounds=0,
    )
    assert event is InterviewEvent.EVAL_NEXT_QUESTION
    assert streak == 1


def test_last_main_round_forces_finalize_on_next() -> None:
    s = _scores(5, 5, 5)
    event, _ = decide_post_evaluation(
        s,
        main_round_index=4,
        follow_ups_in_round=0,
        consecutive_weak_rounds=0,
        policy=EvaluationPolicy(max_main_questions=5),
    )
    assert event is InterviewEvent.EVAL_FINALIZE


def test_consecutive_weak_terminates() -> None:
    policy = EvaluationPolicy(consecutive_weak_to_end=2)
    weak = _scores(2, 2, 3)
    assert is_weak_answer(weak, policy)

    first, streak1 = decide_post_evaluation(
        weak,
        main_round_index=0,
        follow_ups_in_round=2,
        consecutive_weak_rounds=0,
        policy=policy,
    )
    assert first is InterviewEvent.EVAL_NEXT_QUESTION
    assert streak1 == 1

    second, streak2 = decide_post_evaluation(
        weak,
        main_round_index=1,
        follow_ups_in_round=2,
        consecutive_weak_rounds=streak1,
        policy=policy,
    )
    assert second is InterviewEvent.EVAL_FINALIZE
    assert streak2 == 1


def test_next_consecutive_weak_streak_table() -> None:
    assert (
        next_consecutive_weak_streak(
            previous=1,
            chosen_event=InterviewEvent.EVAL_NEXT_QUESTION,
            weak=True,
        )
        == 2
    )
    assert (
        next_consecutive_weak_streak(
            previous=3,
            chosen_event=InterviewEvent.EVAL_NEXT_QUESTION,
            weak=False,
        )
        == 0
    )
    assert (
        next_consecutive_weak_streak(
            previous=3,
            chosen_event=InterviewEvent.EVAL_FOLLOW_UP,
            weak=True,
        )
        == 3
    )
