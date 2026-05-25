"""Early termination when cumulative low-average rounds reach policy threshold."""

from __future__ import annotations

from interview_simulator.business_layer.decision import is_low_average_round
from interview_simulator.business_layer.schemas import EvaluationPolicy, RoundScores
from interview_simulator.model_layer.agents import InterviewAgentOrchestrator
from interview_simulator.model_layer.evaluation_schemas import AnswerEvaluationResult
from fastapi.testclient import TestClient

from interview_simulator.engineering.app import create_app
from tests.test_fakes import FakeComposer, FakeReporter


class LowAvgScorer:
    async def ascore(self, **_: object) -> AnswerEvaluationResult:
        return AnswerEvaluationResult(
            technical_depth=1,
            clarity=0,
            relevance=1,
            reasoning="stub low",
            key_facts=[],
        )


def test_two_low_scored_rounds_finalize_by_default() -> None:
    orch = InterviewAgentOrchestrator(
        interviewer=FakeComposer(),
        scorer=LowAvgScorer(),
        reporter=FakeReporter(),
        use_llm_scoring=True,
        use_llm_report=False,
    )
    client = TestClient(create_app(orchestrator=orch))
    start = client.post(
        "/interview/start",
        json={
            "job_description": "JD",
            "resume": "CV",
            "evaluation_policy": {
                "max_main_questions": 5,
                "max_follow_ups_per_round": 2,
                "low_avg_rounds_to_end": 2,
            },
        },
    )
    sid = start.json()["session_id"]

    a1 = client.post(
        "/interview/ask",
        json={"session_id": sid, "answer": "first low answer with enough text here."},
    )
    assert a1.status_code == 200
    body1 = a1.json()
    assert body1["finalized"] is False
    assert body1["low_avg_round_count"] == 1

    a2 = client.post(
        "/interview/ask",
        json={"session_id": sid, "answer": "second low answer with enough text here."},
    )
    assert a2.status_code == 200
    body2 = a2.json()
    assert body2["finalized"] is True
    assert body2["low_avg_round_count"] == 2
