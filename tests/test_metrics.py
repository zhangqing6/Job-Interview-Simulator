"""Metrics registry and session analytics."""

from interview_simulator.business_layer.schemas import EvaluationPolicy, RoundScores
from interview_simulator.engineering.metrics import get_metrics, observe_ms
from interview_simulator.engineering.service import SessionRecord, build_session_analytics
from interview_simulator.business_layer import InterviewStateMachine, MemoryConfig


def test_observe_ms_records_latency() -> None:
    reg = get_metrics()
    before = reg.snapshot()["latencies_ms"].get("test_op", {}).get("count", 0)
    with observe_ms("test_op"):
        pass
    after = reg.snapshot()["latencies_ms"]["test_op"]["count"]
    assert after == before + 1


def test_build_session_analytics() -> None:
    from interview_simulator.business_layer.schemas import CompletedRoundDTO

    session = SessionRecord(
        session_id="s",
        job_description="JD",
        resume="CV",
        expected_depth="mid",
        policy=EvaluationPolicy(),
        memory_config=MemoryConfig(),
        fsm=InterviewStateMachine(),
        finalize_reason="low_weighted_avg_early",
    )
    session.completed_rounds.append(
        CompletedRoundDTO(
            main_round_index=0,
            follow_ups_in_round_at_submit=0,
            question="Q",
            answer="A",
            scores=RoundScores(technical_depth=1, clarity=0, relevance=1),
        )
    )
    a = build_session_analytics(session)
    assert a["scored_rounds"] == 1
    assert a["weighted_score_mean"] == 0.8
    assert a["finalize_reason"] == "low_weighted_avg_early"
