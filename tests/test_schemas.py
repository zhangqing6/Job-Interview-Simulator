"""Pydantic schema sanity checks for model layer."""

from interview_simulator.model_layer.schemas import (
    GeneratedQuestion,
    QuestionComposerResult,
    QuestionCritique,
)


def test_generated_question_roundtrip() -> None:
    g = GeneratedQuestion(
        chain_of_thought="Probe async I/O given FastAPI on resume.",
        question_text="How would you bound latency under load?",
        expected_depth="mid",
    )
    assert g.question_text.startswith("How")


def test_composer_result() -> None:
    c = QuestionCritique(
        difficulty_adequate=True,
        relevance_adequate=True,
        reasoning="ok",
        improvement_hint=None,
    )
    r = QuestionComposerResult(
        final_question="Q",
        expected_depth="senior",
        was_rewritten=False,
        critique=c,
        initial_question="Q",
    )
    assert r.was_rewritten is False
