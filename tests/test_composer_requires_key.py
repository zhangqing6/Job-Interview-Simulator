"""Composer should fail fast without credentials (no accidental network)."""

import os

import pytest

from interview_simulator.model_layer.chains import InterviewQuestionComposer


def test_composer_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        InterviewQuestionComposer()
