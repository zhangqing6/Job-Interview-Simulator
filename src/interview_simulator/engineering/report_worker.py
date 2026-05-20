"""Shared report generation for HTTP layer and Celery workers."""

from __future__ import annotations

from interview_simulator.business_layer import InterviewState
from interview_simulator.engineering.factory import create_session_store, open_store, close_store
from interview_simulator.model_layer.agents import InterviewAgentOrchestrator


async def run_report_for_session(session_id: str) -> None:
    store = create_session_store()
    await open_store(store)
    try:
        session = await store.get(session_id)
        if session is None or session.fsm.context.state is not InterviewState.FINALIZE:
            return
        if session.llm_report is not None:
            return
        orch = InterviewAgentOrchestrator()
        report = await orch.build_report(
            job_description=session.job_description,
            resume=session.resume,
            memory_context=session.memory.materialize_context_block(),
            rounds=session.completed_rounds,
        )
        if report is not None:
            session.llm_report = report
            session.report_pending = False
            await store.put(session)
    finally:
        await close_store(store)


__all__ = ["run_report_for_session"]
