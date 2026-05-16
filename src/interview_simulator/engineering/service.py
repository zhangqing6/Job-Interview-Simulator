"""Orchestrate FSM + decisions + memory behind the HTTP API."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Literal, Protocol

from fastapi import HTTPException

from interview_simulator.business_layer import (
    InterviewEvent,
    InterviewMemory,
    InterviewState,
    InterviewStateMachine,
    MemoryConfig,
    RoundScores,
    TurnRecord,
    decide_post_evaluation,
    prompt_lane_for_state,
)
from interview_simulator.business_layer.schemas import EvaluationPolicy
from interview_simulator.engineering.api_schemas import (
    CompletedRoundDTO,
    InterviewAskResponse,
    InterviewReportResponse,
    InterviewStartResponse,
    InterviewStatusResponse,
)
from interview_simulator.engineering.store_protocol import SessionStore
from interview_simulator.model_layer.schemas import QuestionComposerResult


class QuestionComposerLike(Protocol):
    def compose(
        self,
        job_description: str,
        resume: str,
        *,
        dimension: str,
        expected_depth: Literal["junior", "mid", "senior"],
    ) -> QuestionComposerResult: ...


@dataclass
class SessionRecord:
    session_id: str
    job_description: str
    resume: str
    interview_dimension: str
    expected_depth: Literal["junior", "mid", "senior"]
    policy: EvaluationPolicy
    memory_config: MemoryConfig
    fsm: InterviewStateMachine
    memory: InterviewMemory = field(default_factory=InterviewMemory)
    current_question: str = ""
    completed_rounds: list[CompletedRoundDTO] = field(default_factory=list)


class InterviewHttpService:
    """Business flow for `/interview/*` routes."""

    def __init__(
        self,
        store: SessionStore,
        composer: QuestionComposerLike,
    ) -> None:
        self._store = store
        self._composer = composer

    async def start(
        self,
        *,
        job_description: str,
        resume: str,
        interview_dimension: str,
        expected_depth: Literal["junior", "mid", "senior"],
        evaluation_policy: EvaluationPolicy | None,
    ) -> InterviewStartResponse:
        sid = str(uuid.uuid4())
        policy = evaluation_policy or EvaluationPolicy()
        fsm = InterviewStateMachine()
        fsm.apply(InterviewEvent.START_SESSION)
        session = SessionRecord(
            session_id=sid,
            job_description=job_description.strip(),
            resume=resume.strip(),
            interview_dimension=interview_dimension,
            expected_depth=expected_depth,
            policy=policy,
            memory_config=MemoryConfig(),
            fsm=fsm,
        )
        q = await self._compose_question(session, dimension=session.interview_dimension)
        session.current_question = q
        session.fsm.apply(InterviewEvent.QUESTION_PREPARED)
        session.memory.append_turn(TurnRecord(role="interviewer", text=q), config=session.memory_config)
        await self._store.put(session)
        ctx = session.fsm.context
        return InterviewStartResponse(
            session_id=sid,
            state=ctx.state.value,
            prompt_lane=prompt_lane_for_state(ctx.state),
            current_question=q,
        )

    async def ask(
        self,
        *,
        session_id: str,
        answer: str,
        scores: RoundScores | None,
    ) -> InterviewAskResponse:
        session = await self._store.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session_id.")
        if session.fsm.context.state is InterviewState.FINALIZE:
            raise HTTPException(status_code=400, detail="Interview already finalized.")
        if session.fsm.context.state is not InterviewState.WAITING_FOR_ANSWER:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot submit an answer in state {session.fsm.context.state.value!r}.",
            )

        rubric = scores or RoundScores(technical_depth=3, clarity=3, relevance=3)
        main_idx = session.fsm.context.main_round_index
        fu = session.fsm.context.follow_ups_in_round

        session.memory.append_turn(TurnRecord(role="candidate", text=answer.strip()), config=session.memory_config)
        session.fsm.apply(InterviewEvent.ANSWER_SUBMITTED)

        event, new_streak = decide_post_evaluation(
            rubric,
            main_round_index=main_idx,
            follow_ups_in_round=fu,
            consecutive_weak_rounds=session.fsm.context.consecutive_weak_rounds,
            policy=session.policy,
        )
        session.fsm.patch_context(consecutive_weak_rounds=new_streak)

        ev_note = (
            f"scores depth={rubric.technical_depth} clarity={rubric.clarity} relevance={rubric.relevance}"
        )
        session.memory.append_round_line(
            main_round_index=main_idx,
            question=session.current_question,
            answer_excerpt=answer.strip(),
            evaluation_excerpt=ev_note,
            config=session.memory_config,
        )
        session.completed_rounds.append(
            CompletedRoundDTO(
                main_round_index=main_idx,
                follow_ups_in_round_at_submit=fu,
                question=session.current_question,
                answer=answer.strip(),
                scores=rubric,
            )
        )

        session.fsm.apply(event)

        if event is InterviewEvent.EVAL_FINALIZE:
            await self._store.put(session)
            return InterviewAskResponse(
                session_id=session_id,
                state=session.fsm.context.state.value,
                prompt_lane=prompt_lane_for_state(session.fsm.context.state),
                finalized=True,
                current_question=None,
                message="Interview ended.",
            )

        if event is InterviewEvent.EVAL_FOLLOW_UP:
            dim = (
                f"Follow-up in the same thread as the prior question. Prior question:\n{session.current_question}"
            )
            fq = await self._compose_question(session, dimension=dim)
            session.current_question = fq
            session.fsm.apply(InterviewEvent.FOLLOW_UP_PREPARED)
            session.memory.append_turn(TurnRecord(role="interviewer", text=fq), config=session.memory_config)
            await self._store.put(session)
            ctx = session.fsm.context
            return InterviewAskResponse(
                session_id=session_id,
                state=ctx.state.value,
                prompt_lane=prompt_lane_for_state(ctx.state),
                finalized=False,
                current_question=fq,
                message="Follow-up question.",
            )

        # EVAL_NEXT_QUESTION
        session.fsm.apply(InterviewEvent.BEGIN_PREPARE_NEXT)
        nq = await self._compose_question(session, dimension=session.interview_dimension)
        session.current_question = nq
        session.fsm.apply(InterviewEvent.QUESTION_PREPARED)
        session.memory.append_turn(TurnRecord(role="interviewer", text=nq), config=session.memory_config)
        await self._store.put(session)
        ctx = session.fsm.context
        return InterviewAskResponse(
            session_id=session_id,
            state=ctx.state.value,
            prompt_lane=prompt_lane_for_state(ctx.state),
            finalized=False,
            current_question=nq,
            message="Next main question.",
        )

    async def status(self, session_id: str) -> InterviewStatusResponse:
        session = await self._store.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session_id.")
        ctx = session.fsm.context
        excerpt = session.memory.materialize_context_block(max_chars=3500)
        return InterviewStatusResponse(
            session_id=session_id,
            state=ctx.state.value,
            prompt_lane=prompt_lane_for_state(ctx.state),
            context=ctx.model_dump(mode="json"),
            current_question=session.current_question,
            memory_context_excerpt=excerpt,
        )

    async def report(self, session_id: str) -> InterviewReportResponse:
        session = await self._store.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session_id.")
        if session.fsm.context.state is not InterviewState.FINALIZE:
            raise HTTPException(status_code=409, detail="Interview not finalized yet.")
        summary = _closing_summary(session)
        return InterviewReportResponse(
            session_id=session_id,
            state=session.fsm.context.state.value,
            rounds=list(session.completed_rounds),
            closing_summary=summary,
        )

    async def _compose_question(self, session: SessionRecord, *, dimension: str) -> str:
        jd = session.job_description
        resume = session.resume
        depth = session.expected_depth
        if hasattr(self._composer, "acompose"):
            result = await self._composer.acompose(  # type: ignore[union-attr]
                jd,
                resume,
                dimension=dimension,
                expected_depth=depth,
            )
        else:
            result = await asyncio.to_thread(
                self._composer.compose,
                jd,
                resume,
                dimension=dimension,
                expected_depth=depth,
            )
        return result.final_question.strip()


def _closing_summary(session: SessionRecord) -> str:
    if not session.completed_rounds:
        return "Interview completed with no recorded rounds."
    last = session.completed_rounds[-1].scores
    avg = (last.technical_depth + last.clarity + last.relevance) / 3.0
    return (
        f"Interview completed across {len(session.completed_rounds)} recorded turn(s). "
        f"Last answer average score: {avg:.2f} / 5."
    )


__all__ = ["InterviewHttpService", "QuestionComposerLike", "SessionRecord"]
