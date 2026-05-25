"""0–5 rubric normalization (no legacy mapping)."""

from interview_simulator.model_layer.score_rubric import RUBRIC_MAX, RUBRIC_MIN, normalize_evaluation_scores


def test_clamp_zero_to_five() -> None:
    out = normalize_evaluation_scores(
        {"technical_depth": -1, "clarity": 6, "relevance": 3},
    )
    assert out["technical_depth"] == RUBRIC_MIN
    assert out["clarity"] == RUBRIC_MAX
    assert out["relevance"] == 3


def test_no_legacy_mapping_of_threes() -> None:
    out = normalize_evaluation_scores(
        {"technical_depth": 3, "clarity": 3, "relevance": 3},
    )
    assert out["technical_depth"] == 3
