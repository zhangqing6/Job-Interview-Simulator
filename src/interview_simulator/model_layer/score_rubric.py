"""Shared 0–5 interview scoring rubric (per-axis: 0 = fail, 5 = excellent)."""

from __future__ import annotations

import re
from typing import Any

RUBRIC_MIN = 0
RUBRIC_MAX = 5

_SCORE_FIELDS = ("technical_depth", "clarity", "relevance")


def coerce_axis_score(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(round(float(raw)))
    text = str(raw).strip()
    if not text:
        return None
    m = re.search(r"(\d+)\s*(?:/\s*5|分|points?)?", text, re.I)
    if m:
        return int(m.group(1))
    return None


def normalize_evaluation_scores(data: dict[str, Any]) -> dict[str, Any]:
    """Clamp each axis to integers 0–5 (no scale mapping)."""

    out = dict(data)
    for field in _SCORE_FIELDS:
        val = coerce_axis_score(out.get(field))
        if val is not None:
            out[field] = max(RUBRIC_MIN, min(RUBRIC_MAX, val))
    return out


__all__ = [
    "RUBRIC_MAX",
    "RUBRIC_MIN",
    "coerce_axis_score",
    "normalize_evaluation_scores",
]
