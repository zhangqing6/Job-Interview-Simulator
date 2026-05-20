"""Prompt strategy field on composer results."""

import inspect
from typing import get_args

from interview_simulator.engineering.api_schemas import PromptStrategy
from interview_simulator.model_layer.chains import InterviewQuestionComposer


def test_prompt_strategy_literal_values() -> None:
    assert "zero_shot" in get_args(PromptStrategy)


def test_composer_exposes_strategy_parameter() -> None:
    sig = inspect.signature(InterviewQuestionComposer.compose)
    assert "prompt_strategy" in sig.parameters
