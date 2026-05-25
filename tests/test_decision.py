"""Scoring → FSM event mapping (0–5 bands)."""

from interview_simulator.business_layer.decision import (
    decide_post_evaluation,
    is_low_average_round,
    is_partial_answer,
    is_satisfactory,
)
from interview_simulator.business_layer.interview_fsm import InterviewEvent
from interview_simulator.business_layer.schemas import EvaluationPolicy, RoundScores
from interview_simulator.model_layer.score_alignment import PriorRound, is_duplicate_across_questions as dup


def _scores(tech: int, clarity: int, rel: int) -> RoundScores:
    return RoundScores(technical_depth=tech, clarity=clarity, relevance=rel)


def test_partial_triggers_follow_up() -> None:
    s = _scores(2, 3, 3)
    assert is_partial_answer(s)
    assert decide_post_evaluation(s, main_round_index=0, follow_ups_in_round=0) is InterviewEvent.EVAL_FOLLOW_UP


def test_satisfactory_goes_next_question() -> None:
    s = _scores(4, 5, 4)
    assert is_satisfactory(s)
    assert decide_post_evaluation(s, main_round_index=0, follow_ups_in_round=0) is InterviewEvent.EVAL_NEXT_QUESTION


def test_low_weighted_detection() -> None:
    assert is_low_average_round(_scores(1, 0, 1))
    assert is_low_average_round(_scores(1, 1, 1))
    assert not is_low_average_round(_scores(1, 1, 2))
    assert not is_low_average_round(_scores(2, 2, 2))


def test_duplicate_detection() -> None:
    q1 = "描述 Redis 持久化"
    q2 = "解释 Kafka 分区策略"
    same = "我使用 RDB 和 AOF 做持久化并定期备份到对象存储。"
    assert dup(q2, same, [PriorRound(question=q1, answer=same)])


def test_last_main_round_forces_finalize() -> None:
    s = _scores(5, 5, 5)
    assert (
        decide_post_evaluation(
            s,
            main_round_index=4,
            follow_ups_in_round=0,
            policy=EvaluationPolicy(max_main_questions=5),
        )
        is InterviewEvent.EVAL_FINALIZE
    )
