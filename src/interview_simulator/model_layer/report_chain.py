"""LLM report agent — report_chain (Roadmap)."""

from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate

from interview_simulator.engineering.api_schemas import CompletedRoundDTO
from interview_simulator.model_layer.llm_factory import create_chat_llm
from interview_simulator.model_layer.observability import log_llm_event
from interview_simulator.model_layer.report_prompts import REPORTER_SYSTEM, REPORTER_USER
from interview_simulator.model_layer.report_schemas import InterviewLLMReport


def _rounds_to_text(rounds: list[CompletedRoundDTO]) -> str:
    rows = []
    for i, r in enumerate(rounds, start=1):
        s = r.scores
        rows.append(
            {
                "round": i,
                "main_round_index": r.main_round_index,
                "question": r.question[:500],
                "answer": r.answer[:500],
                "technical_depth": s.technical_depth,
                "clarity": s.clarity,
                "relevance": s.relevance,
            }
        )
    return json.dumps(rows, ensure_ascii=False, indent=2)


class InterviewReportAgent:
    """Reporter agent: deep feedback report after interview finalize."""

    def __init__(self, llm=None) -> None:
        self._llm = llm or create_chat_llm(agent="reporter", operation="report", temperature=0.4)
        self._chain = ChatPromptTemplate.from_messages(
            [("system", REPORTER_SYSTEM), ("human", REPORTER_USER)]
        ) | self._llm.with_structured_output(InterviewLLMReport)

    def generate(
        self,
        *,
        job_description: str,
        resume: str,
        memory_context: str,
        rounds: list[CompletedRoundDTO],
    ) -> InterviewLLMReport:
        log_llm_event(agent="reporter", operation="generate", status="start")
        result: InterviewLLMReport = self._chain.invoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "memory_context": memory_context.strip() or "(none)",
                "rounds_summary": _rounds_to_text(rounds),
            }
        )
        log_llm_event(agent="reporter", operation="generate", status="ok")
        return result

    async def agenerate(
        self,
        *,
        job_description: str,
        resume: str,
        memory_context: str,
        rounds: list[CompletedRoundDTO],
    ) -> InterviewLLMReport:
        log_llm_event(agent="reporter", operation="agenerate", status="start")
        result: InterviewLLMReport = await self._chain.ainvoke(
            {
                "job_description": job_description.strip(),
                "resume": resume.strip(),
                "memory_context": memory_context.strip() or "(none)",
                "rounds_summary": _rounds_to_text(rounds),
            }
        )
        log_llm_event(agent="reporter", operation="agenerate", status="ok")
        return result


__all__ = ["InterviewReportAgent"]
