"""Serialize ``SessionRecord`` for Redis / multi-instance storage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from interview_simulator.business_layer import (
    InterviewMemory,
    InterviewStateMachine,
    MemoryConfig,
)
from interview_simulator.business_layer.interview_fsm import InterviewSessionContext
from interview_simulator.business_layer.schemas import EvaluationPolicy
from interview_simulator.engineering.api_schemas import CompletedRoundDTO, InterviewLanguage, PromptStrategy
from interview_simulator.engineering.service import SessionRecord
from interview_simulator.model_layer.report_schemas import InterviewLLMReport


class StoredSession(BaseModel):
    """JSON-safe snapshot of an in-flight interview session."""

    session_id: str
    job_description: str
    resume: str
    expected_depth: Literal["junior", "mid", "senior"]
    policy: EvaluationPolicy
    interview_dimension: str | None = None
    memory_config: MemoryConfig
    fsm_context: InterviewSessionContext
    memory: InterviewMemory = Field(default_factory=InterviewMemory)
    current_question: str = ""
    completed_rounds: list[CompletedRoundDTO] = Field(default_factory=list)
    prompt_strategy: PromptStrategy = "cot"
    interview_language: InterviewLanguage = "zh"
    llm_report: InterviewLLMReport | None = None
    report_pending: bool = False
    finalize_reason: str | None = None


def encode_session(record: SessionRecord) -> str:
    stored = StoredSession(
        session_id=record.session_id,
        job_description=record.job_description,
        resume=record.resume,
        interview_dimension=record.interview_dimension,
        expected_depth=record.expected_depth,
        policy=record.policy,
        memory_config=record.memory_config,
        fsm_context=record.fsm.context,
        memory=record.memory,
        current_question=record.current_question,
        completed_rounds=list(record.completed_rounds),
        prompt_strategy=record.prompt_strategy,
        interview_language=record.interview_language,
        llm_report=record.llm_report,
        report_pending=record.report_pending,
        finalize_reason=record.finalize_reason,
    )
    return stored.model_dump_json()


def decode_session(payload: str) -> SessionRecord:
    stored = StoredSession.model_validate_json(payload)
    return SessionRecord(
        session_id=stored.session_id,
        job_description=stored.job_description,
        resume=stored.resume,
        interview_dimension=stored.interview_dimension,
        expected_depth=stored.expected_depth,
        policy=stored.policy,
        memory_config=stored.memory_config,
        fsm=InterviewStateMachine(context=stored.fsm_context),
        memory=stored.memory,
        current_question=stored.current_question,
        completed_rounds=list(stored.completed_rounds),
        prompt_strategy=stored.prompt_strategy,
        interview_language=stored.interview_language,
        llm_report=stored.llm_report,
        report_pending=stored.report_pending,
        finalize_reason=stored.finalize_reason,
    )


__all__ = ["StoredSession", "decode_session", "encode_session"]
