"""Process-local session storage (Engineering ① — before Redis)."""

from __future__ import annotations

import asyncio
from typing import Any


class InMemorySessionStore:
    """Async-safe dict backend; swap for Redis in Engineering ②."""

    def __init__(self) -> None:
        self._sessions: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def put(self, session: Any) -> None:
        async with self._lock:
            self._sessions[session.session_id] = session

    async def get(self, session_id: str) -> Any | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)


__all__ = ["InMemorySessionStore"]
