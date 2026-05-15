"""FastAPI application wiring (Engineering ①)."""

from __future__ import annotations

from fastapi import Depends, FastAPI

from interview_simulator.engineering.api_schemas import (
    InterviewAskRequest,
    InterviewAskResponse,
    InterviewReportResponse,
    InterviewStartRequest,
    InterviewStartResponse,
    InterviewStatusResponse,
)
from interview_simulator.engineering.service import InterviewHttpService, QuestionComposerLike
from interview_simulator.engineering.store import InMemorySessionStore
from interview_simulator.model_layer.chains import InterviewQuestionComposer


def create_app(
    *,
    store: InMemorySessionStore | None = None,
    composer: QuestionComposerLike | None = None,
) -> FastAPI:
    """Build the HTTP service. Pass a fake ``composer`` in tests to avoid network keys."""

    comp: QuestionComposerLike = composer or InterviewQuestionComposer()
    mem_store = store or InMemorySessionStore()
    service = InterviewHttpService(mem_store, comp)

    app = FastAPI(
        title="Job Interview Simulator API",
        version="0.1.0",
        description="FastAPI surface aligned with README `/interview/*` routes (Engineering ①).",
    )

    def get_service() -> InterviewHttpService:
        return service

    @app.post("/interview/start", response_model=InterviewStartResponse)
    async def interview_start(
        body: InterviewStartRequest,
        svc: InterviewHttpService = Depends(get_service),
    ) -> InterviewStartResponse:
        return await svc.start(
            job_description=body.job_description,
            resume=body.resume,
            interview_dimension=body.interview_dimension,
            expected_depth=body.expected_depth,
            evaluation_policy=body.evaluation_policy,
        )

    @app.post("/interview/ask", response_model=InterviewAskResponse)
    async def interview_ask(
        body: InterviewAskRequest,
        svc: InterviewHttpService = Depends(get_service),
    ) -> InterviewAskResponse:
        return await svc.ask(session_id=body.session_id, answer=body.answer, scores=body.scores)

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
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


__all__ = ["create_app"]
