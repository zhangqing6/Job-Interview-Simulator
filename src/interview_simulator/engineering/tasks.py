"""FastAPI ``BackgroundTasks`` helpers — non-blocking side effects after HTTP response."""

from __future__ import annotations

import logging
from typing import Any

from interview_simulator.engineering.store_protocol import SessionStore

logger = logging.getLogger("interview_simulator.audit")


async def audit_session_event(
    store: SessionStore,
    session_id: str,
    *,
    event: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Lightweight post-response audit (Engineering ②). Does not change API contracts."""

    session = await store.get(session_id)
    if session is None:
        logger.warning("audit_missing_session", extra={"session_id": session_id, "event": event})
        return
    ctx = session.fsm.context
    payload = {
        "session_id": session_id,
        "event": event,
        "state": ctx.state.value,
        "main_round_index": ctx.main_round_index,
        "turns_presented": ctx.turns_presented,
        **(extra or {}),
    }
    logger.info("interview_session_event", extra=payload)


__all__ = ["audit_session_event"]
