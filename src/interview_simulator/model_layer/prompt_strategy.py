"""Prompt strategy variants for question generation experiments."""

from __future__ import annotations

from typing import Literal

PromptStrategy = Literal["zero_shot", "few_shot", "cot"]

FEW_SHOT_GENERATION_PREFIX = """Example 1 — JD: backend role, resume: Python/FastAPI.
Question: How would you design idempotent payment webhooks and handle duplicate delivery?

Example 2 — JD: data platform, resume: Spark/Kafka.
Question: Walk through how you would debug consumer lag growing linearly during peak traffic.

Now produce ONE new question for the candidate below (do not copy the examples verbatim).
"""

ZERO_SHOT_GENERATION_SYSTEM = """You are a senior technical interviewer.
Produce ONE focused technical interview question from the JD and resume.
Output structured fields only; keep `question_text` free of meta-commentary.
Do not include chain-of-thought in the candidate-facing question text beyond the structured `chain_of_thought` field.

{language_rule}
"""


__all__ = ["FEW_SHOT_GENERATION_PREFIX", "PromptStrategy", "ZERO_SHOT_GENERATION_SYSTEM"]
