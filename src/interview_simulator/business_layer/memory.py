"""Compact multi-turn memory: rolling summary + key facts + recent tail (README Part 2 ③)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from interview_simulator.business_layer.schemas import TurnRecord


class MemoryConfig(BaseModel):
    """Bounds to keep prompts small without dropping all context."""

    max_tail_turns: int = Field(8, ge=0, description="How many recent turns to retain verbatim.")
    max_key_facts: int = Field(12, ge=0)
    max_summary_chars: int = Field(4000, ge=0)
    max_turn_chars: int = Field(2000, ge=1, description="Per-turn truncation for the tail buffer.")


class InterviewMemory(BaseModel):
    """Session-scoped memory suitable for feeding model prompts alongside JD/resume."""

    rolling_summary: str = Field("", description="Running prose summary of what has been covered.")
    key_facts: list[str] = Field(default_factory=list, description="Short bullets worth recalling later.")
    tail: list[TurnRecord] = Field(default_factory=list, description="Most recent turns (interviewer/candidate).")

    def append_turn(self, turn: TurnRecord, *, config: MemoryConfig | None = None) -> None:
        cfg = config or MemoryConfig()
        text = turn.text if len(turn.text) <= cfg.max_turn_chars else turn.text[: cfg.max_turn_chars] + "…"
        self.tail.append(TurnRecord(role=turn.role, text=text))
        overflow = len(self.tail) - cfg.max_tail_turns
        if overflow > 0:
            self.tail = self.tail[overflow:]

    def append_round_line(
        self,
        *,
        main_round_index: int,
        question: str,
        answer_excerpt: str,
        evaluation_excerpt: str | None = None,
        config: MemoryConfig | None = None,
    ) -> None:
        """Append one human-readable line to ``rolling_summary`` (deterministic, token-cheap)."""

        cfg = config or MemoryConfig()
        ev = f" Notes: {evaluation_excerpt}" if evaluation_excerpt else ""
        line = (
            f"Round {main_round_index + 1}: Q: {question.strip()[:400]} — "
            f"A: {answer_excerpt.strip()[:400]}{ev}\n"
        )
        merged = (self.rolling_summary + line).strip() + "\n"
        if len(merged) > cfg.max_summary_chars:
            merged = merged[-cfg.max_summary_chars :]
        self.rolling_summary = merged

    def add_key_facts(self, facts: list[str], *, config: MemoryConfig | None = None) -> None:
        """Merge deduplicated facts (callers may supply LLM-extracted facts later)."""

        cfg = config or MemoryConfig()
        seen = {f.strip() for f in self.key_facts if f.strip()}
        for raw in facts:
            fact = raw.strip()
            if not fact or fact in seen:
                continue
            self.key_facts.append(fact)
            seen.add(fact)
            if len(self.key_facts) > cfg.max_key_facts:
                self.key_facts = self.key_facts[-cfg.max_key_facts :]

    def materialize_context_block(self, *, max_chars: int = 3500) -> str:
        """Single string block for prompt injection (summary + facts + tail)."""

        parts: list[str] = []
        if self.rolling_summary.strip():
            parts.append("## Interview summary so far\n" + self.rolling_summary.strip())
        if self.key_facts:
            bullets = "\n".join(f"- {f}" for f in self.key_facts)
            parts.append("## Key facts to remember\n" + bullets)
        if self.tail:
            lines = []
            for t in self.tail:
                who = "Interviewer" if t.role == "interviewer" else "Candidate"
                lines.append(f"{who}: {t.text}")
            parts.append("## Recent dialogue (tail)\n" + "\n".join(lines))
        block = "\n\n".join(parts).strip()
        if len(block) > max_chars:
            return block[-max_chars:]
        return block


__all__ = ["InterviewMemory", "MemoryConfig"]
