"""Structured outputs for LLM answer evaluation."""

from pydantic import BaseModel, Field

from interview_simulator.business_layer.schemas import RoundScores


class AnswerEvaluationResult(BaseModel):
    """Scoring agent output — maps to ``RoundScores`` + memory facts."""

    technical_depth: int = Field(..., ge=0, le=5)
    clarity: int = Field(..., ge=0, le=5)
    relevance: int = Field(..., ge=0, le=5)
    reasoning: str = Field(..., description="1–3 sentences justifying the scores.")
    key_facts: list[str] = Field(default_factory=list, max_length=5)

    def to_round_scores(self) -> RoundScores:
        return RoundScores(
            technical_depth=self.technical_depth,
            clarity=self.clarity,
            relevance=self.relevance,
        )


__all__ = ["AnswerEvaluationResult"]
