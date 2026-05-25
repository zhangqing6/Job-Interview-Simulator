"""Resilient question compose and fallback templates."""

from __future__ import annotations

import pytest

from interview_simulator.business_layer import InterviewStateMachine, MemoryConfig
from interview_simulator.business_layer.schemas import EvaluationPolicy
from interview_simulator.engineering.service import InterviewHttpService, SessionRecord
from interview_simulator.model_layer.agents import InterviewAgentOrchestrator
from interview_simulator.model_layer.question_fallback import fallback_question


def test_fallback_question_zh() -> None:
    q = fallback_question(dimension="Redis 缓存", expected_depth="mid", interview_language="zh")
    assert "Redis" in q
    assert "mid" in q


@pytest.mark.asyncio
async def test_compose_question_uses_fallback_when_llm_fails() -> None:
    class BrokenComposer:
        async def acompose(self, *args, **kwargs):
            raise RuntimeError("upstream 500")

    orch = InterviewAgentOrchestrator(
        interviewer=BrokenComposer(),
        use_llm_scoring=False,
        use_llm_report=False,
    )

    class _NoStore:
        async def put(self, session):
            pass

    svc = InterviewHttpService(store=_NoStore(), orchestrator=orch)
    session = SessionRecord(
        session_id="x",
        job_description="JD",
        resume="CV",
        interview_dimension=None,
        expected_depth="mid",
        policy=EvaluationPolicy(),
        memory_config=MemoryConfig(),
        fsm=InterviewStateMachine(),
        prompt_strategy="zero_shot",
        interview_language="zh",
    )
    text = await svc._compose_question(session)
    assert "项目经历" in text
