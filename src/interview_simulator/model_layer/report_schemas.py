"""Structured LLM final interview report."""

from pydantic import BaseModel, Field


class InterviewLLMReport(BaseModel):
    overall_assessment: str = Field(..., description="2–4 sentence holistic view.")
    strengths: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(
        default_factory=list,
        description="Concrete, actionable next steps for the candidate.",
    )
    recommended_study_topics: list[str] = Field(default_factory=list)
    closing_summary: str = Field(..., description="Short wrap-up for recruiters/candidates.")


__all__ = ["InterviewLLMReport"]
