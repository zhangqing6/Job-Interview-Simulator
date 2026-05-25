"""Orchestrate FSM + multi-agent LLM behind the HTTP API."""

from __future__ import annotations

import logging
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
    is_low_average_round,
    prompt_lane_for_state,
)
from interview_simulator.business_layer.schemas import EvaluationPolicy
from interview_simulator.business_layer.score_weighting import weighted_score
from interview_simulator.engineering.api_schemas import (
    CompletedRoundDTO,
    InterviewAskResponse,
    InterviewLanguage,
    InterviewReportResponse,
    InterviewStartResponse,
    InterviewStatusResponse,
    PromptStrategy,
)
from interview_simulator.model_layer.language import (
    duplicate_answer_finalize_message,
    duplicate_answer_warning,
    follow_up_dimension,
    low_avg_finalize_message,
    low_avg_warning_message,
)
from interview_simulator.engineering.celery_app import dispatch_report_task
from interview_simulator.engineering.store_protocol import SessionStore
from interview_simulator.model_layer.agents import InterviewAgentOrchestrator
from interview_simulator.model_layer.dimension import (
    dimension_focus_for_prompt,
    normalize_interview_dimension,
)
from interview_simulator.model_layer.question_fallback import fallback_question
from interview_simulator.model_layer.report_schemas import InterviewLLMReport
from interview_simulator.model_layer.score_alignment import PriorRound, is_duplicate_across_questions

_logger = logging.getLogger(__name__)


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
    prompt_strategy: PromptStrategy = "zero_shot"
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
        prompt_strategy: PromptStrategy = "zero_shot",
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

    def _prior_rounds(self, session: SessionRecord) -> list[PriorRound]:
        return [PriorRound(question=r.question, answer=r.answer) for r in session.completed_rounds]

    @staticmethod
    def _low_avg_meta(session: SessionRecord, *, count: int | None = None) -> dict[str, int]:
        return {
            "low_avg_round_count": count
            if count is not None
            else session.fsm.context.low_avg_round_count,
            "low_avg_rounds_to_end": session.policy.low_avg_rounds_to_end,
        }

    def _append_low_avg_hint(
        self,
        session: SessionRecord,
        *,
        message: str | None,
        low_avg_count: int,
        rubric: RoundScores,
    ) -> str | None:
        if not is_low_average_round(rubric, session.policy):
            return message
        remaining = session.policy.low_avg_rounds_to_end - low_avg_count
        if remaining <= 0:
            return message
        hint = low_avg_warning_message(session.interview_language, remaining=remaining)
        base = message or ""
        return f"{base} {hint}".strip() if base else hint

    async def _handle_duplicate_answer(
        self,
        session: SessionRecord,
        *,
        session_id: str,
        answer: str,
    ) -> InterviewAskResponse:
        ctx = session.fsm.context
        warnings = ctx.duplicate_warning_count + 1
        session.fsm.patch_context(duplicate_warning_count=warnings)
        lang = session.interview_language

        if warnings >= session.policy.duplicate_warnings_to_end:
            session.fsm.apply(InterviewEvent.ANSWER_SUBMITTED)
            session.fsm.apply(InterviewEvent.EVAL_FINALIZE)
            msg = duplicate_answer_finalize_message(lang)
            await self._schedule_report_generation(session)
            await self._store.put(session)
            return InterviewAskResponse(
                session_id=session_id,
                state=session.fsm.context.state.value,
                prompt_lane=prompt_lane_for_state(session.fsm.context.state),
                finalized=True,
                current_question=None,
                message=msg,
                warning=msg,
                scores=None,
                scores_source=None,
                evaluation_reasoning=msg,
            )

        warn = duplicate_answer_warning(lang)
        await self._store.put(session)
        return InterviewAskResponse(
            session_id=session_id,
            state=ctx.state.value,
            prompt_lane=prompt_lane_for_state(ctx.state),
            finalized=False,
            current_question=session.current_question,
            message=warn,
            warning=warn,
            scores=None,
            scores_source=None,
            evaluation_reasoning=warn,
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

        answer = answer.strip()
        if is_duplicate_across_questions(
            session.current_question,
            answer,
            self._prior_rounds(session),
        ):
            return await self._handle_duplicate_answer(session, session_id=session_id, answer=answer)

        rubric, scores_source, reasoning = await self._resolve_scores(
            session,
            answer=answer,
            client_scores=scores,
            use_llm_scoring=use_llm_scoring,
        )
        main_idx = session.fsm.context.main_round_index
        fu = session.fsm.context.follow_ups_in_round

        session.memory.append_turn(TurnRecord(role="candidate", text=answer), config=session.memory_config)
        session.fsm.apply(InterviewEvent.ANSWER_SUBMITTED)

        low_avg_count = session.fsm.context.low_avg_round_count
        if is_low_average_round(rubric, session.policy):
            low_avg_count += 1
        session.fsm.patch_context(low_avg_round_count=low_avg_count)

        if low_avg_count >= session.policy.low_avg_rounds_to_end:
            event = InterviewEvent.EVAL_FINALIZE
        else:
            event = decide_post_evaluation(
                rubric,
                main_round_index=main_idx,
                follow_ups_in_round=fu,
                policy=session.policy,
            )

        ev_note = reasoning or (
            f"scores depth={rubric.technical_depth} clarity={rubric.clarity} relevance={rubric.relevance}"
        )
        session.memory.append_round_line(
            main_round_index=main_idx,
            question=session.current_question,
            answer_excerpt=answer,
            evaluation_excerpt=ev_note,
            config=session.memory_config,
        )
        session.completed_rounds.append(
            CompletedRoundDTO(
                main_round_index=main_idx,
                follow_ups_in_round_at_submit=fu,
                question=session.current_question,
                answer=answer,
                scores=rubric,
            )
        )

        session.fsm.apply(event)

        if event is InterviewEvent.EVAL_FINALIZE:
            end_msg = (
                low_avg_finalize_message(session.interview_language)
                if low_avg_count >= session.policy.low_avg_rounds_to_end
                else "Interview ended."
            )
            await self._schedule_report_generation(session)
            await self._store.put(session)
            return InterviewAskResponse(
                session_id=session_id,
                state=session.fsm.context.state.value,
                prompt_lane=prompt_lane_for_state(session.fsm.context.state),
                finalized=True,
                current_question=None,
                message=end_msg,
                scores=rubric,
                scores_source=scores_source,
                evaluation_reasoning=reasoning,
                **self._low_avg_meta(session, count=low_avg_count),
            )

        if event is InterviewEvent.EVAL_FOLLOW_UP:
            dim = follow_up_dimension(session.interview_language, session.current_question)
            fq = await self._compose_question(session, dimension_override=dim)
            session.current_question = fq
            session.fsm.apply(InterviewEvent.FOLLOW_UP_PREPARED)
            session.memory.append_turn(TurnRecord(role="interviewer", text=fq), config=session.memory_config)
            await self._store.put(session)
            ctx = session.fsm.context
            msg = self._append_low_avg_hint(
                session,
                message="Follow-up question.",
                low_avg_count=low_avg_count,
                rubric=rubric,
            )
            return InterviewAskResponse(
                session_id=session_id,
                state=ctx.state.value,
                prompt_lane=prompt_lane_for_state(ctx.state),
                finalized=False,
                current_question=fq,
                message=msg,
                scores=rubric,
                scores_source=scores_source,
                evaluation_reasoning=reasoning,
                **self._low_avg_meta(session, count=low_avg_count),
            )

        session.fsm.apply(InterviewEvent.BEGIN_PREPARE_NEXT)
        nq = await self._compose_question(session)
        session.current_question = nq
        session.fsm.apply(InterviewEvent.QUESTION_PREPARED)
        session.memory.append_turn(TurnRecord(role="interviewer", text=nq), config=session.memory_config)
        await self._store.put(session)
        ctx = session.fsm.context
        msg = self._append_low_avg_hint(
            session,
            message="Next main question.",
            low_avg_count=low_avg_count,
            rubric=rubric,
        )
        return InterviewAskResponse(
            session_id=session_id,
            state=ctx.state.value,
            prompt_lane=prompt_lane_for_state(ctx.state),
            finalized=False,
            current_question=nq,
            message=msg,
            scores=rubric,
            scores_source=scores_source,
            evaluation_reasoning=reasoning,
            **self._low_avg_meta(session, count=low_avg_count),
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
        strategies: list[PromptStrategy] = [session.prompt_strategy]
        if session.prompt_strategy != "zero_shot":
            strategies.append("zero_shot")

        last_exc: Exception | None = None
        for strategy in strategies:
            try:
                result = await self._orch.compose_question(
                    session.job_description,
                    session.resume,
                    dimension=focus,
                    expected_depth=session.expected_depth,
                    prompt_strategy=strategy,
                    interview_language=session.interview_language,
                )
                text = result.final_question.strip()
                if text:
                    if strategy != session.prompt_strategy:
                        _logger.warning(
                            "compose_question recovered with strategy=%s session=%s",
                            strategy,
                            session.session_id,
                        )
                    return text
            except Exception as exc:
                last_exc = exc
                _logger.warning(
                    "compose_question failed strategy=%s session=%s: %s",
                    strategy,
                    session.session_id,
                    exc,
                )

        fb = fallback_question(
            dimension=focus,
            expected_depth=session.expected_depth,
            interview_language=session.interview_language,
        )
        _logger.error(
            "compose_question using fallback session=%s last_error=%s",
            session.session_id,
            last_exc,
        )
        return fb


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
    w = weighted_score(last)
    n = len(session.completed_rounds)
    if session.interview_language == "zh":
        return (
            f"面试结束，共记录 {n} 轮作答，最后一轮加权分 {w:.2f} / 5"
            f"（0.3×技术+0.2×清晰+0.5×相关）。"
        )
    return (
        f"Interview completed across {n} recorded turn(s). "
        f"Last weighted score: {w:.2f} / 5 (0.3×depth + 0.2×clarity + 0.5×relevance)."
    )


__all__ = ["InterviewHttpService", "SessionRecord"]
