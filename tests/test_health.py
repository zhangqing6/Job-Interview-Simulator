"""Liveness / readiness helpers."""

import pytest
from fakeredis import aioredis as fakeredis_aioredis

from interview_simulator.engineering.health import build_health_payload, check_readiness
from interview_simulator.engineering.redis_store import RedisSessionStore
from interview_simulator.engineering.store import InMemorySessionStore


@pytest.mark.asyncio
async def test_memory_backend_always_ready() -> None:
    store = InMemorySessionStore()
    ready, details = await check_readiness(store)
    assert ready is True
    assert details["backend"] == "memory"


@pytest.mark.asyncio
async def test_redis_backend_ready_when_ping_ok() -> None:
    client = fakeredis_aioredis.FakeRedis(decode_responses=True)
    store = RedisSessionStore.from_client(client)
    ready, details = await check_readiness(store)
    assert ready is True
    assert details["redis"] is True


@pytest.mark.asyncio
async def test_health_payload_memory() -> None:
    payload = await build_health_payload(InMemorySessionStore())
    assert payload["status"] == "ok"
    assert payload["backend"] == "memory"
