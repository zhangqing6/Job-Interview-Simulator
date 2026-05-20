"""End-to-end HTTP flow across start → ask → status → report (Engineering ③)."""

from __future__ import annotations

from fakeredis import aioredis as fakeredis_aioredis
from fastapi.testclient import TestClient

from interview_simulator.engineering.app import create_app
from interview_simulator.engineering.redis_store import RedisSessionStore
from interview_simulator.model_layer.agents import InterviewAgentOrchestrator
from tests.test_fakes import FakeComposer, FakeReporter, FakeScorer


def _orch() -> InterviewAgentOrchestrator:
    return InterviewAgentOrchestrator(
        interviewer=FakeComposer(),
        scorer=FakeScorer(),
        reporter=FakeReporter(),
        use_llm_scoring=True,
        use_llm_report=True,
    )


def _client(*, redis: bool = False) -> TestClient:
    if redis:
        store = RedisSessionStore.from_client(
            fakeredis_aioredis.FakeRedis(decode_responses=True)
        )
        return TestClient(create_app(orchestrator=_orch(), store=store))
    return TestClient(create_app(orchestrator=_orch()))


def test_full_interview_lifecycle_memory() -> None:
    client = _client()
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").status_code == 200

    start = client.post(
        "/interview/start",
        json={
            "job_description": "Backend engineer for payments.",
            "resume": "Python, FastAPI, PostgreSQL.",
            "interview_dimension": "distributed systems",
            "expected_depth": "mid",
            "evaluation_policy": {"max_main_questions": 2, "max_follow_ups_per_round": 1},
        },
    )
    assert start.status_code == 200
    sid = start.json()["session_id"]
    assert start.headers.get("x-request-id")

    ask1 = client.post(
        "/interview/ask",
        json={
            "session_id": sid,
            "answer": "I would shard by tenant id and use outbox pattern with metrics.",
        },
    )
    assert ask1.status_code == 200
    assert ask1.json()["finalized"] is False

    ask2 = client.post(
        "/interview/ask",
        json={
            "session_id": sid,
            "answer": "For the second question I would add circuit breakers and dashboards.",
        },
    )
    assert ask2.status_code == 200
    assert ask2.json()["finalized"] is True

    status = client.get(f"/interview/status/{sid}")
    assert status.status_code == 200
    assert status.json()["state"] == "finalize"
    assert "memory_context_excerpt" in status.json()

    report = client.get(f"/interview/report/{sid}")
    assert report.status_code == 200
    body = report.json()
    assert len(body["rounds"]) == 2
    assert body["closing_summary"]
    assert body["report_source"] == "llm"
    assert body["improvement_suggestions"]


def test_full_interview_lifecycle_redis_backend() -> None:
    client = _client(redis=True)
    assert client.get("/readyz").json()["ready"] is True
    assert client.get("/healthz").json()["backend"] == "redis"

    sid = client.post(
        "/interview/start",
        json={"job_description": "JD", "resume": "CV", "evaluation_policy": {"max_main_questions": 1}},
    ).json()["session_id"]

    client.post(
        "/interview/ask",
        json={
            "session_id": sid,
            "answer": "done",
            "scores": {"technical_depth": 5, "clarity": 5, "relevance": 5},
        },
    )
    assert client.get(f"/interview/report/{sid}").status_code == 200


def test_report_409_before_finalize() -> None:
    client = _client()
    sid = client.post(
        "/interview/start",
        json={"job_description": "JD", "resume": "CV"},
    ).json()["session_id"]
    assert client.get(f"/interview/report/{sid}").status_code == 409
