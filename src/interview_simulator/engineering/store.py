"""In-memory session backend (dev / single-process fallback)."""

from __future__ import annotations

import asyncio
import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from interview_simulator.engineering.service import SessionRecord


class InMemorySessionStore:
    """Async-safe dict backend when ``REDIS_URL`` is unset."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def put(self, session: SessionRecord) -> None:
        async with self._lock:
            self._sessions[session.session_id] = copy.deepcopy(session)

    async def get(self, session_id: str) -> SessionRecord | None:
        async with self._lock:
            found = self._sessions.get(session_id)
            return copy.deepcopy(found) if found is not None else None

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def ping(self) -> bool:
        return True


__all__ = ["InMemorySessionStore"]
