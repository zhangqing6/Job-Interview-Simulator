"""Redis session store (fakeredis — no live server required)."""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fakeredis_aioredis
from fastapi.testclient import TestClient

from interview_simulator.business_layer import InterviewStateMachine, MemoryConfig
from interview_simulator.business_layer.schemas import EvaluationPolicy
from interview_simulator.engineering.app import create_app
from interview_simulator.engineering.redis_store import RedisSessionStore
from interview_simulator.engineering.service import SessionRecord
from interview_simulator.engineering.session_codec import decode_session, encode_session
from tests.test_api import FakeComposer


@pytest.fixture
def fake_redis_store() -> RedisSessionStore:
    client = fakeredis_aioredis.FakeRedis(decode_responses=True)
    return RedisSessionStore.from_client(client, ttl_seconds=60)


@pytest.mark.asyncio
async def test_redis_put_get_delete(fake_redis_store: RedisSessionStore) -> None:
    record = SessionRecord(
        session_id="sess-1",
        job_description="JD",
        resume="CV",
        interview_dimension="tech",
        expected_depth="mid",
        policy=EvaluationPolicy(),
        memory_config=MemoryConfig(),
        fsm=InterviewStateMachine(),
    )
    await fake_redis_store.put(record)
    loaded = await fake_redis_store.get("sess-1")
    assert loaded is not None
    assert loaded.session_id == "sess-1"
    assert loaded.job_description == "JD"

    await fake_redis_store.delete("sess-1")
    assert await fake_redis_store.get("sess-1") is None


def test_codec_payload_is_json_object() -> None:
    record = SessionRecord(
        session_id="sess-2",
        job_description="A",
        resume="B",
        interview_dimension="d",
        expected_depth="junior",
        policy=EvaluationPolicy(),
        memory_config=MemoryConfig(),
        fsm=InterviewStateMachine(),
        current_question="Q?",
    )
    decode_session(encode_session(record))


@pytest.mark.asyncio
async def test_redis_ping(fake_redis_store: RedisSessionStore) -> None:
    assert await fake_redis_store.ping() is True


def test_api_end_to_end_with_redis_store(fake_redis_store: RedisSessionStore) -> None:
    app = create_app(composer=FakeComposer(), store=fake_redis_store)
    client = TestClient(app)

    r = client.post(
        "/interview/start",
        json={"job_description": "JD", "resume": "CV", "evaluation_policy": {"max_main_questions": 1}},
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]

    health = client.get("/healthz").json()
    assert health["backend"] == "redis"
    assert health["redis"] is True

    r2 = client.post(
        "/interview/ask",
        json={
            "session_id": sid,
            "answer": "answer",
            "scores": {"technical_depth": 5, "clarity": 5, "relevance": 5},
        },
    )
    assert r2.status_code == 200
    assert r2.json()["finalized"] is True
