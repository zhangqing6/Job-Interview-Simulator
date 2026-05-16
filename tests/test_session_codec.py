"""Session JSON codec for Redis persistence."""

from interview_simulator.business_layer import InterviewEvent, InterviewStateMachine, MemoryConfig
from interview_simulator.business_layer.schemas import EvaluationPolicy
from interview_simulator.engineering.session_codec import decode_session, encode_session
from interview_simulator.engineering.service import SessionRecord


def test_encode_decode_roundtrip() -> None:
    fsm = InterviewStateMachine()
    fsm.apply(InterviewEvent.START_SESSION)
    record = SessionRecord(
        session_id="abc-123",
        job_description="JD text",
        resume="Resume text",
        interview_dimension="systems",
        expected_depth="senior",
        policy=EvaluationPolicy(),
        memory_config=MemoryConfig(),
        fsm=fsm,
        current_question="Tell me about caching.",
    )

    restored = decode_session(encode_session(record))
    assert restored.session_id == record.session_id
    assert restored.current_question == record.current_question
    assert restored.fsm.context.state == record.fsm.context.state
