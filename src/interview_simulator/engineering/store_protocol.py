"""Session storage abstraction (Engineering ②)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from interview_simulator.engineering.service import SessionRecord


@runtime_checkable
class SessionStore(Protocol):
    async def put(self, session: SessionRecord) -> None: ...
    async def get(self, session_id: str) -> SessionRecord | None: ...
    async def delete(self, session_id: str) -> None: ...


class SupportsStoreHealth(Protocol):
    async def ping(self) -> bool: ...


__all__ = ["SessionStore", "SupportsStoreHealth"]
