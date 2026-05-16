"""FastAPI application wiring (Engineering ① + ②)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI

from interview_simulator.engineering.api_schemas import (
    InterviewAskRequest,
    InterviewAskResponse,
    InterviewReportResponse,
    InterviewStartRequest,
    InterviewStartResponse,
    InterviewStatusResponse,
)
from interview_simulator.engineering.factory import close_store, create_session_store, open_store
from interview_simulator.engineering.service import InterviewHttpService, QuestionComposerLike
from interview_simulator.engineering.store_protocol import SessionStore
from interview_simulator.engineering.tasks import audit_session_event
from interview_simulator.model_layer.chains import InterviewQuestionComposer, load_dotenv_if_present


def create_app(
    *,
    store: SessionStore | None = None,
    composer: QuestionComposerLike | None = None,
) -> FastAPI:
    """Build the HTTP service. Pass ``store`` / ``composer`` overrides in tests."""

    load_dotenv_if_present()
    session_store: SessionStore = store or create_session_store()
    comp: QuestionComposerLike = composer or InterviewQuestionComposer()
    service = InterviewHttpService(session_store, comp)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = session_store
        app.state.service = service
        await open_store(session_store)
        try:
            yield
        finally:
            await close_store(session_store)

    app = FastAPI(
        title="Job Interview Simulator API",
        version="0.2.0",
        description="FastAPI + optional Redis sessions (Engineering ①②).",
        lifespan=lifespan,
    )

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
        resp = await svc.start(
            job_description=body.job_description,
            resume=body.resume,
            interview_dimension=body.interview_dimension,
            expected_depth=body.expected_depth,
            evaluation_policy=body.evaluation_policy,
        )
        background_tasks.add_task(
            audit_session_event,
            st,
            resp.session_id,
            event="start",
            extra={"state": resp.state},
        )
        return resp

    @app.post("/interview/ask", response_model=InterviewAskResponse)
    async def interview_ask(
        body: InterviewAskRequest,
        background_tasks: BackgroundTasks,
        svc: InterviewHttpService = Depends(get_service),
        st: SessionStore = Depends(get_store),
    ) -> InterviewAskResponse:
        resp = await svc.ask(session_id=body.session_id, answer=body.answer, scores=body.scores)
        background_tasks.add_task(
            audit_session_event,
            st,
            body.session_id,
            event="ask",
            extra={"finalized": resp.finalized, "state": resp.state},
        )
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
        backend = "redis" if type(st).__name__ == "RedisSessionStore" else "memory"
        payload: dict[str, Any] = {"status": "ok", "backend": backend}
        if hasattr(st, "ping"):
            redis_ok = await st.ping()  # type: ignore[union-attr]
            payload["redis"] = redis_ok
            if backend == "redis" and not redis_ok:
                payload["status"] = "degraded"
        return payload

    return app


__all__ = ["create_app"]
