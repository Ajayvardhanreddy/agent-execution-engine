import pytest

from engine.orchestrator.state_machine import (
    TERMINAL_STATES,
    TRANSITIONS,
    AgentState,
    validate_transition,
)


def test_all_states_have_transition_entry():
    for state in AgentState:
        assert state in TRANSITIONS, f"{state} missing from TRANSITIONS"


def test_terminal_states_have_no_transitions():
    for state in TERMINAL_STATES:
        assert TRANSITIONS[state] == frozenset()


def test_valid_transition_does_not_raise():
    validate_transition(AgentState.START, AgentState.LOAD_MEMORY)
    validate_transition(AgentState.CALL_LLM, AgentState.PROCESS_RESPONSE)
    validate_transition(AgentState.CALL_LLM, AgentState.FAIL)


def test_invalid_transition_raises():
    with pytest.raises(ValueError, match="Invalid transition"):
        validate_transition(AgentState.START, AgentState.CALL_LLM)


def test_start_leads_to_load_memory():
    assert AgentState.LOAD_MEMORY in TRANSITIONS[AgentState.START]


def test_execute_tool_can_escalate():
    assert AgentState.ESCALATE in TRANSITIONS[AgentState.EXECUTE_TOOL]


def test_process_response_cannot_go_to_fail():
    assert AgentState.FAIL not in TRANSITIONS[AgentState.PROCESS_RESPONSE]
