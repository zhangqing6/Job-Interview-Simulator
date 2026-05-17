"""Liveness / readiness checks for orchestrators (Engineering ③)."""

from __future__ import annotations

from typing import Any

from interview_simulator.engineering.store_protocol import SessionStore


def session_backend_name(store: SessionStore) -> str:
    return "redis" if type(store).__name__ == "RedisSessionStore" else "memory"


async def check_readiness(store: SessionStore) -> tuple[bool, dict[str, Any]]:
    """Ready when the process can serve traffic (Redis reachable when configured)."""

    backend = session_backend_name(store)
    details: dict[str, Any] = {"backend": backend}
    if backend == "memory":
        return True, details
    if not hasattr(store, "ping"):
        details["redis"] = False
        details["reason"] = "store_missing_ping"
        return False, details
    redis_ok = await store.ping()  # type: ignore[union-attr]
    details["redis"] = redis_ok
    if not redis_ok:
        details["reason"] = "redis_unreachable"
    return redis_ok, details


async def build_health_payload(store: SessionStore) -> dict[str, Any]:
    """Liveness payload for ``/healthz`` (process up; may be degraded)."""

    backend = session_backend_name(store)
    payload: dict[str, Any] = {"status": "ok", "backend": backend}
    if hasattr(store, "ping"):
        redis_ok = await store.ping()  # type: ignore[union-attr]
        payload["redis"] = redis_ok
        if backend == "redis" and not redis_ok:
            payload["status"] = "degraded"
    return payload


__all__ = ["build_health_payload", "check_readiness", "session_backend_name"]
