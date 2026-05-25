"""Weighted score 0.3 / 0.2 / 0.5."""

from interview_simulator.business_layer.decision import (
    is_low_average_round,
    is_partial_answer,
    is_satisfactory,
)
from interview_simulator.business_layer.schemas import RoundScores
from interview_simulator.business_layer.score_weighting import weighted_score


def test_weighted_formula() -> None:
    s = RoundScores(technical_depth=2, clarity=0, relevance=2)
    assert weighted_score(s) == 0.3 * 2 + 0.2 * 0 + 0.5 * 2


def test_low_weighted_not_simple_average() -> None:
    s = RoundScores(technical_depth=1, clarity=1, relevance=2)
    assert weighted_score(s) == 1.5
    assert is_low_average_round(s)


def test_above_low_threshold() -> None:
    s = RoundScores(technical_depth=2, clarity=2, relevance=3)
    assert weighted_score(s) > 1.5
    assert not is_low_average_round(s)


def test_low_weighted_counts() -> None:
    assert is_low_average_round(RoundScores(technical_depth=1, clarity=0, relevance=1))


def test_partial_and_satisfactory_use_weighted() -> None:
    partial = RoundScores(technical_depth=2, clarity=2, relevance=3)
    assert 2.3 <= weighted_score(partial) < 4.0
    assert is_partial_answer(partial)
    good = RoundScores(technical_depth=5, clarity=4, relevance=5)
    assert is_satisfactory(good)
