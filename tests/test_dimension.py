"""Optional interview dimension focus."""

from interview_simulator.model_layer.dimension import (
    dimension_focus_for_prompt,
    normalize_interview_dimension,
)


def test_normalize_blank_to_none() -> None:
    assert normalize_interview_dimension(None) is None
    assert normalize_interview_dimension("") is None
    assert normalize_interview_dimension("   ") is None
    assert normalize_interview_dimension("  API design  ") == "API design"


def test_auto_focus_when_dimension_missing() -> None:
    zh = dimension_focus_for_prompt(None, interview_language="zh")
    assert "未指定" in zh
    en = dimension_focus_for_prompt(None, interview_language="en")
    assert "No interview dimension" in en


def test_explicit_dimension_passthrough() -> None:
    assert dimension_focus_for_prompt("分布式系统", interview_language="zh") == "分布式系统"
