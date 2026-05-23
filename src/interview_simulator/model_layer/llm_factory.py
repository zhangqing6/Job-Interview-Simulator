"""Shared ChatOpenAI construction (Zhipu GLM via OpenAI-compatible API)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from interview_simulator.model_layer.observability import get_token_handler

DEFAULT_JUDGE_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
DEFAULT_JUDGE_MODEL = "glm-4"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class LlmConfig:
    api_key: str
    base_url: str
    model: str


def resolve_llm_config(*, model_override: str | None = None) -> LlmConfig:
    """Read ``JUDGE_*`` env vars (OpenAI-compatible endpoint for GLM)."""

    api_key = os.getenv("JUDGE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "JUDGE_API_KEY is not set. Copy .env.example to .env and set your Zhipu (BigModel) API key."
        )
    base_url = (os.getenv("JUDGE_BASE_URL", "").strip() or DEFAULT_JUDGE_BASE_URL).rstrip("/") + "/"
    model = model_override or os.getenv("JUDGE_MODEL", "").strip() or DEFAULT_JUDGE_MODEL
    return LlmConfig(api_key=api_key, base_url=base_url, model=model)


def create_chat_llm(
    *,
    model: str | None = None,
    temperature: float = 0.3,
    agent: str = "llm",
    operation: str = "invoke",
) -> ChatOpenAI:
    cfg = resolve_llm_config(model_override=model)
    return ChatOpenAI(
        model=cfg.model,
        temperature=temperature,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        callbacks=[get_token_handler(agent=agent, operation=operation)],
    )


def create_llm(
    *,
    model: str | None = None,
    temperature: float = 0.3,
    agent: str = "llm",
    operation: str = "invoke",
) -> ChatOpenAI:
    """Alias for :func:`create_chat_llm`."""
    return create_chat_llm(
        model=model,
        temperature=temperature,
        agent=agent,
        operation=operation,
    )


def create_judge_llm(
    *,
    model: str | None = None,
    temperature: float = 0.0,
) -> ChatOpenAI:
    """GLM client for scoring / critique (deterministic temperature by default)."""
    return create_chat_llm(
        model=model,
        temperature=temperature,
        agent="judge",
        operation="judge",
    )


def llm_enabled() -> bool:
    """True when ``JUDGE_API_KEY`` is configured."""
    return bool(os.getenv("JUDGE_API_KEY", "").strip())


def is_llm_scoring_enabled() -> bool:
    return llm_enabled() and _env_bool("USE_LLM_SCORING", True)


def is_llm_report_enabled() -> bool:
    return llm_enabled() and _env_bool("USE_LLM_REPORT", True)


__all__ = [
    "DEFAULT_JUDGE_BASE_URL",
    "DEFAULT_JUDGE_MODEL",
    "LlmConfig",
    "create_chat_llm",
    "create_judge_llm",
    "create_llm",
    "is_llm_report_enabled",
    "is_llm_scoring_enabled",
    "llm_enabled",
    "resolve_llm_config",
]
