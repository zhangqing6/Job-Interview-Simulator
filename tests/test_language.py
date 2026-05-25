"""Interview language wiring."""

from interview_simulator.model_layer.language import (
    follow_up_dimension,
    question_language_rule,
    report_language_rule,
    scorer_language_rule,
)


def test_question_language_rule_zh() -> None:
    assert "简体中文" in question_language_rule("zh")


def test_follow_up_dimension_zh() -> None:
    dim = follow_up_dimension("zh", "上一题内容")
    assert "简体中文" in dim
    assert "上一题内容" in dim


def test_report_and_scorer_rules() -> None:
    assert "English" in report_language_rule("en")
    assert "English" in scorer_language_rule("en")
