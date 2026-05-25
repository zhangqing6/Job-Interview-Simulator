"""Weighted combination of the three scoring axes (must sum to 1.0)."""

from __future__ import annotations

from interview_simulator.business_layer.schemas import RoundScores

WEIGHT_TECHNICAL_DEPTH = 0.3
WEIGHT_CLARITY = 0.2
WEIGHT_RELEVANCE = 0.5


def weighted_score(scores: RoundScores) -> float:
    """0.3×技术深度 + 0.2×表达清晰 + 0.5×相关性."""

    return (
        WEIGHT_TECHNICAL_DEPTH * scores.technical_depth
        + WEIGHT_CLARITY * scores.clarity
        + WEIGHT_RELEVANCE * scores.relevance
    )


__all__ = [
    "WEIGHT_CLARITY",
    "WEIGHT_RELEVANCE",
    "WEIGHT_TECHNICAL_DEPTH",
    "weighted_score",
]
