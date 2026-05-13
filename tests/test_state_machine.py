"""FSM transitions and counters for business layer Part 2a."""

import pytest

from interview_simulator.business_layer import (
    InterviewEvent,
    InterviewSessionContext,
    InterviewState,
    InterviewStateMachine,
    InvalidStateTransition,
    prompt_lane_for_state,
)


def test_happy_path_main_round_and_finalize() -> None:
    m = InterviewStateMachine()
    assert m.context.state is InterviewState.INITIAL

    m.apply(InterviewEvent.START_SESSION)
    assert m.context.state is InterviewState.QUESTIONING

    m.apply(InterviewEvent.QUESTION_PREPARED)
    assert m.context.state is InterviewState.WAITING_FOR_ANSWER
    assert m.context.turns_presented == 1

    m.apply(InterviewEvent.ANSWER_SUBMITTED)
    assert m.context.state is InterviewState.EVALUATING

    m.apply(InterviewEvent.EVAL_NEXT_QUESTION)
    assert m.context.state is InterviewState.NEXT_QUESTION
    assert m.context.follow_ups_in_round == 0

    m.apply(InterviewEvent.BEGIN_PREPARE_NEXT)
    assert m.context.state is InterviewState.QUESTIONING
    assert m.context.main_round_index == 1

    m.apply(InterviewEvent.QUESTION_PREPARED)
    assert m.context.turns_presented == 2

    m.apply(InterviewEvent.ANSWER_SUBMITTED)
    m.apply(InterviewEvent.EVAL_FINALIZE)
    assert m.context.state is InterviewState.FINALIZE


def test_follow_up_branch_increments_follow_up_counter() -> None:
    m = InterviewStateMachine()
    m.apply(InterviewEvent.START_SESSION)
    m.apply(InterviewEvent.QUESTION_PREPARED)
    m.apply(InterviewEvent.ANSWER_SUBMITTED)
    m.apply(InterviewEvent.EVAL_FOLLOW_UP)
    assert m.context.follow_ups_in_round == 1
    assert m.context.state is InterviewState.FOLLOW_UP

    m.apply(InterviewEvent.FOLLOW_UP_PREPARED)
    assert m.context.state is InterviewState.WAITING_FOR_ANSWER
    assert m.context.turns_presented == 2


def test_invalid_transition_raises() -> None:
    m = InterviewStateMachine()
    with pytest.raises(InvalidStateTransition):
        m.apply(InterviewEvent.QUESTION_PREPARED)


def test_finalize_is_terminal() -> None:
    m = InterviewStateMachine(
        InterviewSessionContext(state=InterviewState.FINALIZE, transition_steps=3)
    )
    assert m.allowed_events() == []
    with pytest.raises(InvalidStateTransition):
        m.apply(InterviewEvent.START_SESSION)


def test_prompt_lane_mapping() -> None:
    assert prompt_lane_for_state(InterviewState.QUESTIONING) == "question_chain"
    assert prompt_lane_for_state(InterviewState.FOLLOW_UP) == "follow_up_chain"
