"""Structured outputs for the model capability layer."""

from typing import Literal

from pydantic import BaseModel, Field


class GeneratedQuestion(BaseModel):
    """A single interview question with brief CoT rationale (not shown to candidate)."""

    chain_of_thought: str = Field(
        ...,
        description="Brief internal reasoning: what to probe and why, given JD and resume.",
    )
    question_text: str = Field(
        ...,
        description="The actual question posed to the candidate, clear and technical.",
    )
    expected_depth: Literal["junior", "mid", "senior"] = Field(
        ...,
        description="Target difficulty band this question aims at.",
    )


class QuestionCritique(BaseModel):
    """Self-critique on difficulty and relevance (README: 自检难度 / 挑战性)."""

    difficulty_adequate: bool = Field(
        ...,
        description="True if the question is sufficiently challenging for the stated level.",
    )
    relevance_adequate: bool = Field(
        ...,
        description="True if the question is well tied to JD and resume, not generic trivia.",
    )
    reasoning: str = Field(
        ...,
        description="Short justification for the two booleans.",
    )
    improvement_hint: str | None = Field(
        default=None,
        description="Concrete hint for rewrite if any flag is false.",
    )


class QuestionComposerResult(BaseModel):
    """Final artifact after generate → critique → optional rewrite."""

    final_question: str
    expected_depth: Literal["junior", "mid", "senior"]
    was_rewritten: bool
    critique: QuestionCritique
    initial_question: str
    prompt_strategy: Literal["zero_shot", "few_shot", "cot"] = "cot"
