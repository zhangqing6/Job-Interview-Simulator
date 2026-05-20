"""Optional Celery worker for background LLM report generation (Roadmap)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

_celery_app: Any = None


def get_celery_app():
    global _celery_app
    if _celery_app is not None:
        return _celery_app
    broker = os.getenv("CELERY_BROKER_URL", "").strip()
    if not broker:
        return None
    try:
        from celery import Celery
    except ImportError:
        return None
    _celery_app = Celery("interview_simulator", broker=broker, backend=broker)
    _celery_app.conf.task_serializer = "json"
    _celery_app.conf.result_serializer = "json"
    _celery_app.conf.accept_content = ["json"]
    return _celery_app


def dispatch_report_task(session_id: str) -> bool:
    """Enqueue report precomputation; returns True if dispatched to Celery."""

    app = get_celery_app()
    if app is None:
        return False
    app.send_task("interview_simulator.generate_llm_report", args=[session_id])
    return True


def register_tasks() -> None:
    app = get_celery_app()
    if app is None:
        return

    @app.task(name="interview_simulator.generate_llm_report")
    def generate_llm_report(session_id: str) -> dict[str, str]:
        from interview_simulator.engineering.report_worker import run_report_for_session

        asyncio.run(run_report_for_session(session_id))
        return {"session_id": session_id, "status": "ok"}


register_tasks()

__all__ = ["dispatch_report_task", "get_celery_app"]
