"""Shared ChatOpenAI construction with observability callbacks."""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

from interview_simulator.model_layer.observability import get_token_handler


def create_chat_llm(
    *,
    model: str | None = None,
    temperature: float = 0.3,
    agent: str = "llm",
    operation: str = "invoke",
) -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it or load a .env file before invoking LLM agents."
        )
    return ChatOpenAI(
        model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=temperature,
        api_key=api_key,
        callbacks=[get_token_handler(agent=agent, operation=operation)],
    )


def llm_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


__all__ = ["create_chat_llm", "llm_enabled"]
