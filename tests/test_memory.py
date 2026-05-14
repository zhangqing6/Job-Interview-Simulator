"""Compact interview memory (business layer Part 2 ③)."""

from interview_simulator.business_layer.memory import InterviewMemory, MemoryConfig
from interview_simulator.business_layer.schemas import TurnRecord


def test_tail_truncation_and_max_turns() -> None:
    mem = InterviewMemory()
    cfg = MemoryConfig(max_tail_turns=2, max_turn_chars=10)
    mem.append_turn(TurnRecord(role="interviewer", text="123456789012"), config=cfg)
    mem.append_turn(TurnRecord(role="candidate", text="abcdefghijklmnop"), config=cfg)
    mem.append_turn(TurnRecord(role="interviewer", text="latest"), config=cfg)
    assert len(mem.tail) == 2
    assert mem.tail[0].text.endswith("…")


def test_key_facts_dedupe_and_cap() -> None:
    mem = InterviewMemory()
    cfg = MemoryConfig(max_key_facts=2)
    mem.add_key_facts(["a", "b", "a", "c"], config=cfg)
    assert mem.key_facts == ["b", "c"]


def test_materialize_context_block_respects_budget() -> None:
    mem = InterviewMemory(rolling_summary="x" * 5000, key_facts=["fact"])
    block = mem.materialize_context_block(max_chars=200)
    assert len(block) == 200
