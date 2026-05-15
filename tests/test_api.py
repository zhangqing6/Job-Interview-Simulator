"""HTTP API smoke tests (no OpenAI key — fake composer)."""

from __future__ import annotations

from typing import Literal

from fastapi.testclient import TestClient

from interview_simulator.engineering.app import create_app
from interview_simulator.model_layer.schemas import QuestionComposerResult, QuestionCritique


class FakeComposer:
    def __init__(self) -> None:
        self._n = 0

    def compose(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str,
        expected_depth: Literal["junior", "mid", "senior"],
    ) -> QuestionComposerResult:
        self._n += 1
        q = f"Q{self._n}: ({expected_depth}) {dimension[:40]}"
        crit = QuestionCritique(
            difficulty_adequate=True,
            relevance_adequate=True,
            reasoning="stub",
            improvement_hint=None,
        )
        return QuestionComposerResult(
            final_question=q,
            expected_depth=expected_depth,
            was_rewritten=False,
            critique=crit,
            initial_question=q,
        )


def test_start_ask_finalize_and_report() -> None:
    app = create_app(composer=FakeComposer())
    client = TestClient(app)

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
            "answer": "I would use idempotency keys and retries.",
            "scores": {"technical_depth": 5, "clarity": 5, "relevance": 5},
        },
    )
    assert r2.status_code == 200, r2.text
    ask = r2.json()
    assert ask["finalized"] is True
    assert ask["state"] == "finalize"

    r409 = client.get(f"/interview/report/{sid}")
    assert r409.status_code == 200
    rep = r409.json()
    assert rep["state"] == "finalize"
    assert len(rep["rounds"]) == 1

    st = client.get(f"/interview/status/{sid}")
    assert st.status_code == 200
    assert st.json()["state"] == "finalize"


def test_follow_up_then_next_question() -> None:
    app = create_app(composer=FakeComposer())
    client = TestClient(app)

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
        json={
            "session_id": sid,
            "answer": "vague",
            "scores": {"technical_depth": 2, "clarity": 2, "relevance": 3},
        },
    )
    assert r2.status_code == 200
    assert r2.json()["finalized"] is False
    assert "Follow-up" in (r2.json().get("message") or "")
    assert r2.json()["current_question"].startswith("Q2:")

    r3 = client.post(
        "/interview/ask",
        json={
            "session_id": sid,
            "answer": "better detail now",
            "scores": {"technical_depth": 5, "clarity": 5, "relevance": 5},
        },
    )
    assert r3.status_code == 200
    assert r3.json()["finalized"] is False
    assert r3.json()["current_question"].startswith("Q3:")


def test_unknown_session_returns_404() -> None:
    app = create_app(composer=FakeComposer())
    client = TestClient(app)
    assert client.get("/interview/status/00000000-0000-0000-0000-000000000000").status_code == 404


def test_report_before_finalize_is_409() -> None:
    app = create_app(composer=FakeComposer())
    client = TestClient(app)
    sid = client.post(
        "/interview/start",
        json={"job_description": "JD", "resume": "CV"},
    ).json()["session_id"]
    assert client.get(f"/interview/report/{sid}").status_code == 409


def test_healthz() -> None:
    app = create_app(composer=FakeComposer())
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}
