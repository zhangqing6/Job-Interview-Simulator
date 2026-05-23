"""SSE streaming for interviewer question text (Roadmap)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate

from interview_simulator.model_layer.language import (
    InterviewLanguage,
    question_language_rule,
    stream_language_suffix,
)
from interview_simulator.model_layer.llm_factory import create_chat_llm
from interview_simulator.model_layer.prompt_strategy import (
    FEW_SHOT_GENERATION_PREFIX,
    PromptStrategy,
    ZERO_SHOT_GENERATION_SYSTEM,
)
from interview_simulator.model_layer.prompts import GENERATION_SYSTEM, GENERATION_USER


def _generation_system(strategy: PromptStrategy) -> str:
    if strategy == "zero_shot":
        return ZERO_SHOT_GENERATION_SYSTEM
    if strategy == "few_shot":
        return FEW_SHOT_GENERATION_PREFIX + "\n" + GENERATION_SYSTEM
    return GENERATION_SYSTEM


async def astream_question_tokens(
    job_description: str,
    resume: str,
    *,
    dimension: str = "technical depth",
    expected_depth: Literal["junior", "mid", "senior"] = "mid",
    prompt_strategy: PromptStrategy = "cot",
    interview_language: InterviewLanguage = "zh",
) -> AsyncIterator[str]:
    """Yield raw token text from the interviewer LLM (non-structured stream)."""

    llm = create_chat_llm(agent="interviewer", operation="astream", temperature=0.4)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _generation_system(prompt_strategy)),
            (
                "human",
                GENERATION_USER
                + stream_language_suffix(interview_language),
            ),
        ]
    )
    chain = prompt | llm
    async for chunk in chain.astream(
        {
            "job_description": job_description.strip(),
            "resume": resume.strip(),
            "dimension": dimension,
            "expected_depth": expected_depth,
            "language_rule": question_language_rule(interview_language),
        }
    ):
        if chunk.content:
            yield chunk.content if isinstance(chunk.content, str) else str(chunk.content)


def sse_encode(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


__all__ = ["astream_question_tokens", "sse_encode"]
