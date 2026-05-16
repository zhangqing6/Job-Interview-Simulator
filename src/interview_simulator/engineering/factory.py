"""Select session backend from environment (Engineering ②)."""

from __future__ import annotations

import os

from interview_simulator.engineering.redis_store import RedisSessionStore
from interview_simulator.engineering.store import InMemorySessionStore
from interview_simulator.engineering.store_protocol import SessionStore


def create_session_store(*, redis_url: str | None = None) -> SessionStore:
    """Use Redis when ``REDIS_URL`` (or explicit ``redis_url``) is set; else in-memory."""

    url = (redis_url if redis_url is not None else os.getenv("REDIS_URL", "")).strip()
    if url:
        ttl = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
        return RedisSessionStore(url, ttl_seconds=ttl)
    return InMemorySessionStore()


async def open_store(store: SessionStore) -> None:
    if hasattr(store, "connect"):
        await store.connect()  # type: ignore[attr-defined]


async def close_store(store: SessionStore) -> None:
    if hasattr(store, "close"):
        await store.close()  # type: ignore[attr-defined]


__all__ = ["close_store", "create_session_store", "open_store"]
