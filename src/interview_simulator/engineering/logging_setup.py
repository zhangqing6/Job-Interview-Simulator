"""Structured logging (JSON Lines) for production observability (Engineering ③)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

STANDARD_LOGRECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "taskName",
    }
)


class JsonLinesFormatter(logging.Formatter):
    """One JSON object per log line (JSONL-friendly)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in STANDARD_LOGRECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(
    *,
    log_format: str | None = None,
    log_level: str | None = None,
) -> None:
    """Configure root logging from ``LOG_FORMAT`` / ``LOG_LEVEL`` env vars."""

    fmt = (log_format or os.getenv("LOG_FORMAT", "text")).strip().lower()
    level_name = (log_level or os.getenv("LOG_LEVEL", "INFO")).strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    if fmt in ("json", "jsonl"):
        handler.setFormatter(JsonLinesFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
    root.addHandler(handler)
    root.setLevel(level)


__all__ = ["JsonLinesFormatter", "configure_logging"]
