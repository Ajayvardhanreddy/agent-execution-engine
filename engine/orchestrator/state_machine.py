from __future__ import annotations

from enum import Enum


class AgentState(str, Enum):
    START             = "START"
    LOAD_MEMORY       = "LOAD_MEMORY"
    BUILD_CONTEXT     = "BUILD_CONTEXT"
    CALL_LLM          = "CALL_LLM"
    PROCESS_RESPONSE  = "PROCESS_RESPONSE"
    EXECUTE_TOOL      = "EXECUTE_TOOL"
    OBSERVE_RESULT    = "OBSERVE_RESULT"
    WRITE_MEMORY      = "WRITE_MEMORY"
    CHECK_TERMINATION = "CHECK_TERMINATION"
    RESPOND           = "RESPOND"
    ESCALATE          = "ESCALATE"
    FAIL              = "FAIL"


TERMINAL_STATES: frozenset[AgentState] = frozenset({
    AgentState.RESPOND,
    AgentState.ESCALATE,
    AgentState.FAIL,
})

# Valid next states for each state
TRANSITIONS: dict[AgentState, frozenset[AgentState]] = {
    AgentState.START:             frozenset({AgentState.LOAD_MEMORY}),
    AgentState.LOAD_MEMORY:       frozenset({AgentState.BUILD_CONTEXT, AgentState.FAIL}),
    AgentState.BUILD_CONTEXT:     frozenset({AgentState.CALL_LLM}),
    AgentState.CALL_LLM:          frozenset({AgentState.PROCESS_RESPONSE, AgentState.FAIL}),
    AgentState.PROCESS_RESPONSE:  frozenset({AgentState.EXECUTE_TOOL, AgentState.RESPOND, AgentState.ESCALATE}),
    AgentState.EXECUTE_TOOL:      frozenset({AgentState.OBSERVE_RESULT, AgentState.ESCALATE, AgentState.FAIL}),
    AgentState.OBSERVE_RESULT:    frozenset({AgentState.WRITE_MEMORY}),
    AgentState.WRITE_MEMORY:      frozenset({AgentState.CHECK_TERMINATION}),
    AgentState.CHECK_TERMINATION: frozenset({AgentState.CALL_LLM, AgentState.RESPOND, AgentState.ESCALATE, AgentState.FAIL}),
    AgentState.RESPOND:           frozenset(),
    AgentState.ESCALATE:          frozenset(),
    AgentState.FAIL:              frozenset(),
}


def validate_transition(from_state: AgentState, to_state: AgentState) -> None:
    allowed = TRANSITIONS.get(from_state, frozenset())
    if to_state not in allowed:
        raise ValueError(
            f"Invalid transition: {from_state.value} → {to_state.value}. "
            f"Allowed: {[s.value for s in allowed]}"
        )
