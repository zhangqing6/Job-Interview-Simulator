"""Token-level LLM call logging (Engineering / Roadmap observability)."""

from __future__ import annotations

import logging
import threading
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("interview_simulator.llm")

_handler_lock = threading.Lock()
_token_handler: TokenUsageCallbackHandler | None = None


class TokenUsageCallbackHandler(BaseCallbackHandler):
    """Emit one JSON-friendly log line per LLM completion with usage metadata."""

    def __init__(self, *, agent: str = "unknown", operation: str = "invoke") -> None:
        self.agent = agent
        self.operation = operation

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        usage: dict[str, Any] = {}
        if response.llm_output:
            usage = response.llm_output.get("token_usage") or response.llm_output.get("usage") or {}
        generations = response.generations[0] if response.generations else []
        model_name = None
        if generations and generations[0].generation_info:
            model_name = generations[0].generation_info.get("model_name")
        logger.info(
            "llm_token_usage",
            extra={
                "agent": self.agent,
                "operation": self.operation,
                "model": model_name,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        )


def get_token_handler(*, agent: str, operation: str) -> TokenUsageCallbackHandler:
    return TokenUsageCallbackHandler(agent=agent, operation=operation)


def log_llm_event(
    *,
    agent: str,
    operation: str,
    status: str,
    extra: dict[str, Any] | None = None,
) -> None:
    logger.info(
        "llm_call",
        extra={"agent": agent, "operation": operation, "status": status, **(extra or {})},
    )


__all__ = ["TokenUsageCallbackHandler", "get_token_handler", "log_llm_event"]
