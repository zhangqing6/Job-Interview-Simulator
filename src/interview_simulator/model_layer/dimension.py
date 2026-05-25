"""Interview dimension: optional user focus vs auto-infer from JD + resume."""

from __future__ import annotations

from interview_simulator.model_layer.language import InterviewLanguage

_AUTO_FOCUS_ZH = (
    "（未指定面试维度）请结合职位描述与简历中的项目经历、技术栈与岗位职责，"
    "自主选择最有考察价值的技术方向生成一题（如系统架构、性能与稳定性、"
    "分布式/数据一致性、工程实践、业务场景理解等），避免空泛套话。"
)
_AUTO_FOCUS_EN = (
    "(No interview dimension specified) From the JD and resume, choose the most "
    "valuable technical angle for one question (e.g. architecture, performance, "
    "reliability, distributed systems, engineering practice, domain understanding). "
    "Ground the question in concrete signals from the materials."
)


def normalize_interview_dimension(raw: str | None) -> str | None:
    """Return stripped focus text, or ``None`` when the client leaves dimension blank."""

    if raw is None:
        return None
    text = raw.strip()
    return text or None


def dimension_focus_for_prompt(
    interview_dimension: str | None,
    *,
    interview_language: InterviewLanguage = "zh",
) -> str:
    """Prompt ``dimension`` field: user focus, or instructions to infer from JD/resume."""

    if interview_dimension:
        return interview_dimension
    return _AUTO_FOCUS_ZH if interview_language == "zh" else _AUTO_FOCUS_EN


__all__ = ["dimension_focus_for_prompt", "normalize_interview_dimension"]
