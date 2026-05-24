"""Orchestrate FSM + multi-agent LLM behind the HTTP API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

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
    InterviewLanguage,
    InterviewReportResponse,
    InterviewStartResponse,
    InterviewStatusResponse,
    PromptStrategy,
)
from interview_simulator.model_layer.language import follow_up_dimension
from interview_simulator.engineering.celery_app import dispatch_report_task
from interview_simulator.engineering.store_protocol import SessionStore
from interview_simulator.model_layer.agents import InterviewAgentOrchestrator
from interview_simulator.model_layer.dimension import (
    dimension_focus_for_prompt,
    normalize_interview_dimension,
)
from interview_simulator.model_layer.report_schemas import InterviewLLMReport
from interview_simulator.model_layer.score_alignment import PriorRound


@dataclass
class SessionRecord:
    session_id: str
    job_description: str
    resume: str
    expected_depth: Literal["junior", "mid", "senior"]
    policy: EvaluationPolicy
    memory_config: MemoryConfig
    fsm: InterviewStateMachine
    interview_dimension: str | None = None
    memory: InterviewMemory = field(default_factory=InterviewMemory)
    current_question: str = ""
    completed_rounds: list[CompletedRoundDTO] = field(default_factory=list)
    prompt_strategy: PromptStrategy = "cot"
    interview_language: InterviewLanguage = "zh"
    llm_report: InterviewLLMReport | None = None
    report_pending: bool = False


class InterviewHttpService:
    """Business flow for `/interview/*` routes."""

    def __init__(
        self,
        store: SessionStore,
        orchestrator: InterviewAgentOrchestrator,
    ) -> None:
        self._store = store
        self._orch = orchestrator

    async def start(
        self,
        *,
        job_description: str,
        resume: str,
        interview_dimension: str | None,
        expected_depth: Literal["junior", "mid", "senior"],
        evaluation_policy: EvaluationPolicy | None,
        prompt_strategy: PromptStrategy = "cot",
        interview_language: InterviewLanguage = "zh",
    ) -> InterviewStartResponse:
        sid = str(uuid.uuid4())
        policy = evaluation_policy or EvaluationPolicy()
        fsm = InterviewStateMachine()
        fsm.apply(InterviewEvent.START_SESSION)
        session = SessionRecord(
            session_id=sid,
            job_description=job_description.strip(),
            resume=resume.strip(),
            interview_dimension=normalize_interview_dimension(interview_dimension),
            expected_depth=expected_depth,
            policy=policy,
            memory_config=MemoryConfig(),
            fsm=fsm,
            prompt_strategy=prompt_strategy,
            interview_language=interview_language,
        )
        q = await self._compose_question(session)
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
            prompt_strategy=prompt_strategy,
            interview_language=interview_language,
        )

    async def ask(
        self,
        *,
        session_id: str,
        answer: str,
        scores: RoundScores | None,
        use_llm_scoring: bool | None = None,
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

        rubric, scores_source, reasoning = await self._resolve_scores(
            session,
            answer=answer.strip(),
            client_scores=scores,
            use_llm_scoring=use_llm_scoring,
        )
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

        ev_note = reasoning or (
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
            await self._schedule_report_generation(session)
            await self._store.put(session)
            return InterviewAskResponse(
                session_id=session_id,
                state=session.fsm.context.state.value,
                prompt_lane=prompt_lane_for_state(session.fsm.context.state),
                finalized=True,
                current_question=None,
                message="Interview ended.",
                scores=rubric,
                scores_source=scores_source,
                evaluation_reasoning=reasoning,
            )

        if event is InterviewEvent.EVAL_FOLLOW_UP:
            dim = follow_up_dimension(session.interview_language, session.current_question)
            fq = await self._compose_question(session, dimension_override=dim)
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
                scores=rubric,
                scores_source=scores_source,
                evaluation_reasoning=reasoning,
            )

        session.fsm.apply(InterviewEvent.BEGIN_PREPARE_NEXT)
        nq = await self._compose_question(session)
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
            scores=rubric,
            scores_source=scores_source,
            evaluation_reasoning=reasoning,
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
            report_ready=session.llm_report is not None,
        )

    async def report(self, session_id: str) -> InterviewReportResponse:
        session = await self._store.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session_id.")
        if session.fsm.context.state is not InterviewState.FINALIZE:
            raise HTTPException(status_code=409, detail="Interview not finalized yet.")
        if session.llm_report is None and self._orch.use_llm_report:
            llm = await self._orch.build_report(
                job_description=session.job_description,
                resume=session.resume,
                memory_context=session.memory.materialize_context_block(),
                rounds=session.completed_rounds,
                interview_language=session.interview_language,
            )
            if llm is not None:
                session.llm_report = llm
                session.report_pending = False
                await self._store.put(session)

        return _build_report_response(session)

    async def _resolve_scores(
        self,
        session: SessionRecord,
        *,
        answer: str,
        client_scores: RoundScores | None,
        use_llm_scoring: bool | None,
    ) -> tuple[RoundScores, Literal["client", "llm", "heuristic"], str | None]:
        if client_scores is not None:
            return client_scores, "client", None

        prior = [
            PriorRound(question=r.question, answer=r.answer) for r in session.completed_rounds
        ]
        llm_on = self._orch.use_llm_scoring if use_llm_scoring is None else use_llm_scoring
        if llm_on:
            eval_result = await self._orch.score_answer(
                job_description=session.job_description,
                resume=session.resume,
                question=session.current_question,
                answer=answer,
                interview_language=session.interview_language,
                prior_rounds=prior,
            )
            if eval_result.key_facts:
                session.memory.add_key_facts(eval_result.key_facts, config=session.memory_config)
            return eval_result.to_round_scores(), "llm", eval_result.reasoning

        eval_result = await self._orch.score_answer(
            job_description=session.job_description,
            resume=session.resume,
            question=session.current_question,
            answer=answer,
            interview_language=session.interview_language,
            prior_rounds=prior,
        )
        return eval_result.to_round_scores(), "heuristic", eval_result.reasoning

    async def _schedule_report_generation(self, session: SessionRecord) -> None:
        if not self._orch.use_llm_report:
            return
        session.report_pending = True
        dispatch_report_task(session.session_id)

    async def _compose_question(
        self,
        session: SessionRecord,
        *,
        dimension_override: str | None = None,
    ) -> str:
        focus = dimension_override or dimension_focus_for_prompt(
            session.interview_dimension,
            interview_language=session.interview_language,
        )
        result = await self._orch.compose_question(
            session.job_description,
            session.resume,
            dimension=focus,
            expected_depth=session.expected_depth,
            prompt_strategy=session.prompt_strategy,
            interview_language=session.interview_language,
        )
        return result.final_question.strip()


def _build_report_response(session: SessionRecord) -> InterviewReportResponse:
    if session.llm_report is not None:
        r = session.llm_report
        return InterviewReportResponse(
            session_id=session.session_id,
            state=session.fsm.context.state.value,
            rounds=list(session.completed_rounds),
            closing_summary=r.closing_summary,
            overall_assessment=r.overall_assessment,
            strengths=list(r.strengths),
            improvement_suggestions=list(r.improvement_suggestions),
            recommended_study_topics=list(r.recommended_study_topics),
            report_source="llm",
            report_pending=session.report_pending,
        )
    summary = _closing_summary(session)
    return InterviewReportResponse(
        session_id=session.session_id,
        state=session.fsm.context.state.value,
        rounds=list(session.completed_rounds),
        closing_summary=summary,
        report_source="heuristic",
        report_pending=session.report_pending,
    )


def _closing_summary(session: SessionRecord) -> str:
    if not session.completed_rounds:
        return (
            "面试结束，无有效答题记录。"
            if session.interview_language == "zh"
            else "Interview completed with no recorded rounds."
        )
    last = session.completed_rounds[-1].scores
    avg = (last.technical_depth + last.clarity + last.relevance) / 3.0
    n = len(session.completed_rounds)
    if session.interview_language == "zh":
        return f"面试结束，共记录 {n} 轮作答，最后一轮均分 {avg:.2f} / 5。"
    return (
        f"Interview completed across {n} recorded turn(s). "
        f"Last answer average score: {avg:.2f} / 5."
    )


__all__ = ["InterviewHttpService", "SessionRecord"]
