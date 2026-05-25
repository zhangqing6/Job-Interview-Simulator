"""Deterministic interview questions when LLM compose fails or times out."""

from __future__ import annotations

from interview_simulator.model_layer.language import InterviewLanguage


def fallback_question(
    *,
    dimension: str,
    expected_depth: str,
    interview_language: InterviewLanguage = "zh",
) -> str:
    topic = (dimension or "technical depth").strip()[:120]
    if interview_language == "zh":
        return (
            f"请结合你的项目经历，具体说明你在「{topic}」方面的实践："
            f"背景、你的方案、关键取舍与结果。（期望深度：{expected_depth}）"
        )
    return (
        f"Based on your experience, walk through a concrete example related to "
        f'"{topic}": context, your approach, trade-offs, and outcomes '
        f"(expected depth: {expected_depth})."
    )


__all__ = ["fallback_question"]
