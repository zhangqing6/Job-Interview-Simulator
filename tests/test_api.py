"""HTTP API smoke tests (fake multi-agent — no OpenAI)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from interview_simulator.engineering.app import create_app
from interview_simulator.model_layer.agents import InterviewAgentOrchestrator
from tests.test_fakes import FakeComposer, FakeReporter, FakeScorer


def _client() -> TestClient:
    orch = InterviewAgentOrchestrator(
        interviewer=FakeComposer(),
        scorer=FakeScorer(),
        reporter=FakeReporter(),
        use_llm_scoring=True,
        use_llm_report=True,
    )
    return TestClient(create_app(orchestrator=orch))


def test_ui_index_served() -> None:
    client = _client()
    r = client.get("/")
    assert r.status_code == 200
    assert "智能面试官" in r.text
    assert client.get("/static/css/app.css").status_code == 200


def test_start_ask_finalize_and_report() -> None:
    client = _client()

    r = client.post(
        "/interview/start",
        json={
            "job_description": "Hiring a backend engineer.",
            "resume": "Python, FastAPI, Redis.",
            "interview_dimension": "API design",
            "expected_depth": "mid",
            "evaluation_policy": {"max_main_questions": 1},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    sid = body["session_id"]
    assert body["state"] == "waiting_for_answer"
    assert body["current_question"].startswith("Q1:")

    r2 = client.post(
        "/interview/ask",
        json={
            "session_id": sid,
            "answer": "I would use idempotency keys and retries with detailed metrics.",
            "scores": None,
        },
    )
    assert r2.status_code == 200, r2.text
    ask = r2.json()
    assert ask["finalized"] is True
    assert ask["scores_source"] == "llm"
    assert ask["scores"]["technical_depth"] == 5

    rep = client.get(f"/interview/report/{sid}")
    assert rep.status_code == 200
    report = rep.json()
    assert report["report_source"] == "llm"
    assert len(report["improvement_suggestions"]) >= 1
    assert report["overall_assessment"]

    st = client.get(f"/interview/status/{sid}")
    assert st.status_code == 200
    assert st.json()["report_ready"] is True


def test_follow_up_then_next_question() -> None:
    client = _client()

    r = client.post(
        "/interview/start",
        json={
            "job_description": "Backend role.",
            "resume": "Go and Postgres.",
            "evaluation_policy": {"max_main_questions": 3, "max_follow_ups_per_round": 2},
        },
    )
    sid = r.json()["session_id"]

    r2 = client.post(
        "/interview/ask",
        json={"session_id": sid, "answer": "vague"},
    )
    assert r2.status_code == 200
    assert r2.json()["finalized"] is False
    assert "Follow-up" in (r2.json().get("message") or "")
    assert r2.json()["scores_source"] == "llm"
    assert r2.json()["scores"]["technical_depth"] == 2

    r3 = client.post(
        "/interview/ask",
        json={
            "session_id": sid,
            "answer": "better detail now with metrics and architecture diagram",
        },
    )
    assert r3.status_code == 200
    assert r3.json()["finalized"] is False
    assert r3.json()["current_question"].startswith("Q3:")


def test_client_scores_override_llm() -> None:
    client = _client()
    sid = client.post(
        "/interview/start",
        json={"job_description": "JD", "resume": "CV", "evaluation_policy": {"max_main_questions": 1}},
    ).json()["session_id"]
    r = client.post(
        "/interview/ask",
        json={
            "session_id": sid,
            "answer": "short",
            "scores": {"technical_depth": 1, "clarity": 1, "relevance": 1},
        },
    )
    assert r.json()["scores_source"] == "client"


def test_unknown_session_returns_404() -> None:
    client = _client()
    assert client.get("/interview/status/00000000-0000-0000-0000-000000000000").status_code == 404


def test_report_before_finalize_is_409() -> None:
    client = _client()
    sid = client.post(
        "/interview/start",
        json={"job_description": "JD", "resume": "CV"},
    ).json()["session_id"]
    assert client.get(f"/interview/report/{sid}").status_code == 409


def test_healthz() -> None:
    body = _client().get("/healthz").json()
    assert body["status"] == "ok"
    assert body["backend"] == "memory"
