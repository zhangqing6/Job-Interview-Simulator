"""FastAPI application wiring (Engineering ①②③ + Roadmap agents)."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from interview_simulator.business_layer import InterviewEvent, InterviewStateMachine, MemoryConfig, TurnRecord
from interview_simulator.business_layer.schemas import EvaluationPolicy
from interview_simulator.engineering.api_schemas import (
    InterviewAskRequest,
    InterviewAskResponse,
    InterviewReportResponse,
    InterviewStartRequest,
    InterviewStartResponse,
    InterviewStatusResponse,
)
from interview_simulator.engineering.factory import close_store, create_session_store, open_store
from interview_simulator.engineering.health import build_health_payload, check_readiness
from interview_simulator.engineering.logging_setup import configure_logging
from interview_simulator.engineering.middleware import RequestLoggingMiddleware
from interview_simulator.engineering.report_worker import run_report_for_session
from interview_simulator.engineering.service import InterviewHttpService, SessionRecord
from interview_simulator.engineering.store_protocol import SessionStore
from interview_simulator.engineering.tasks import audit_session_event
from interview_simulator.model_layer.agents import InterviewAgentOrchestrator, ReporterLike, ScorerLike
from interview_simulator.model_layer.chains import InterviewQuestionComposer, load_dotenv_if_present
from interview_simulator.model_layer.dimension import dimension_focus_for_prompt, normalize_interview_dimension
from interview_simulator.model_layer.streaming import astream_question_tokens, sse_encode

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    *,
    store: SessionStore | None = None,
    orchestrator: InterviewAgentOrchestrator | None = None,
    composer: Any | None = None,
    scorer: ScorerLike | None = None,
    reporter: ReporterLike | None = None,
    enable_request_logging: bool = True,
) -> FastAPI:
    """Build the HTTP service. Pass agent fakes in tests to avoid live LLM calls."""

    load_dotenv_if_present()
    session_store: SessionStore = store or create_session_store()
    orch = orchestrator or InterviewAgentOrchestrator(
        interviewer=composer,
        scorer=scorer,
        reporter=reporter,
    )
    service = InterviewHttpService(session_store, orch)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        app.state.store = session_store
        app.state.service = service
        app.state.orchestrator = orch
        await open_store(session_store)
        try:
            yield
        finally:
            await close_store(session_store)

    app = FastAPI(
        title="Job Interview Simulator API",
        version="0.4.0",
        description="Multi-agent interview API with LLM scoring, reports, SSE, optional Celery.",
        lifespan=lifespan,
    )

    if enable_request_logging:
        app.add_middleware(RequestLoggingMiddleware)

    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

        @app.get("/", include_in_schema=False)
        async def interview_ui() -> FileResponse:
            return FileResponse(_STATIC_DIR / "index.html")

    def get_service() -> InterviewHttpService:
        return service

    def get_store() -> SessionStore:
        return session_store

    @app.post("/interview/start", response_model=InterviewStartResponse)
    async def interview_start(
        body: InterviewStartRequest,
        background_tasks: BackgroundTasks,
        svc: InterviewHttpService = Depends(get_service),
        st: SessionStore = Depends(get_store),
    ) -> InterviewStartResponse:
        if body.stream:
            raise HTTPException(
                status_code=400,
                detail="Use POST /interview/start/stream when stream=true.",
            )
        resp = await svc.start(
            job_description=body.job_description,
            resume=body.resume,
            interview_dimension=body.interview_dimension,
            expected_depth=body.expected_depth,
            evaluation_policy=body.evaluation_policy,
            prompt_strategy=body.prompt_strategy,
            interview_language=body.interview_language,
        )
        background_tasks.add_task(
            audit_session_event,
            st,
            resp.session_id,
            event="start",
            extra={
                "state": resp.state,
                "prompt_strategy": body.prompt_strategy,
                "interview_language": body.interview_language,
            },
        )
        return resp

    @app.post("/interview/start/stream")
    async def interview_start_stream(
        body: InterviewStartRequest,
        st: SessionStore = Depends(get_store),
    ) -> StreamingResponse:
        """SSE stream of interviewer tokens, then persists session with final question."""

        sid = str(uuid.uuid4())
        policy = body.evaluation_policy or EvaluationPolicy()
        fsm = InterviewStateMachine()
        fsm.apply(InterviewEvent.START_SESSION)
        session = SessionRecord(
            session_id=sid,
            job_description=body.job_description.strip(),
            resume=body.resume.strip(),
            interview_dimension=normalize_interview_dimension(body.interview_dimension),
            expected_depth=body.expected_depth,
            policy=policy,
            memory_config=MemoryConfig(),
            fsm=fsm,
            prompt_strategy=body.prompt_strategy,
            interview_language=body.interview_language,
        )

        async def event_gen():
            buffer: list[str] = []
            focus = dimension_focus_for_prompt(
                session.interview_dimension,
                interview_language=session.interview_language,
            )
            try:
                async for token in astream_question_tokens(
                    session.job_description,
                    session.resume,
                    dimension=focus,
                    expected_depth=session.expected_depth,
                    prompt_strategy=body.prompt_strategy,
                    interview_language=body.interview_language,
                ):
                    buffer.append(token)
                    yield sse_encode("token", {"text": token})
            except Exception as exc:
                yield sse_encode("error", {"message": str(exc)})
                return

            question = "".join(buffer).strip()
            if not question:
                question = (
                    "请描述你最近解决过的一个技术难题。"
                    if body.interview_language == "zh"
                    else "Please describe a recent technical challenge you solved."
                )
            session.current_question = question
            session.fsm.apply(InterviewEvent.QUESTION_PREPARED)
            session.memory.append_turn(
                TurnRecord(role="interviewer", text=question),
                config=session.memory_config,
            )
            await st.put(session)
            yield sse_encode(
                "done",
                {
                    "session_id": sid,
                    "state": session.fsm.context.state.value,
                    "current_question": question,
                    "prompt_strategy": body.prompt_strategy,
                },
            )

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    @app.post("/interview/ask", response_model=InterviewAskResponse)
    async def interview_ask(
        body: InterviewAskRequest,
        background_tasks: BackgroundTasks,
        svc: InterviewHttpService = Depends(get_service),
        st: SessionStore = Depends(get_store),
    ) -> InterviewAskResponse:
        resp = await svc.ask(
            session_id=body.session_id,
            answer=body.answer,
            scores=body.scores,
            use_llm_scoring=body.use_llm_scoring,
        )
        background_tasks.add_task(
            audit_session_event,
            st,
            body.session_id,
            event="ask",
            extra={
                "finalized": resp.finalized,
                "state": resp.state,
                "scores_source": resp.scores_source,
            },
        )
        if resp.finalized and orch.use_llm_report:
            background_tasks.add_task(run_report_for_session, body.session_id)
        return resp

    @app.get("/interview/status/{session_id}", response_model=InterviewStatusResponse)
    async def interview_status(
        session_id: str,
        svc: InterviewHttpService = Depends(get_service),
    ) -> InterviewStatusResponse:
        return await svc.status(session_id)

    @app.get("/interview/report/{session_id}", response_model=InterviewReportResponse)
    async def interview_report(
        session_id: str,
        svc: InterviewHttpService = Depends(get_service),
    ) -> InterviewReportResponse:
        return await svc.report(session_id)

    @app.get("/healthz")
    async def healthz(st: SessionStore = Depends(get_store)) -> dict[str, Any]:
        return await build_health_payload(st)

    @app.get("/readyz")
    async def readyz(st: SessionStore = Depends(get_store)) -> Response:
        ready, details = await check_readiness(st)
        body = {"ready": ready, **details}
        status = 200 if ready else 503
        return Response(
            content=json.dumps(body),
            media_type="application/json",
            status_code=status,
        )

    return app


__all__ = ["create_app"]
