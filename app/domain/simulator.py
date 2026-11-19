from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.domain.models import (
    ApiCallNode, AskQuestionNode, AssignTeamNode, ChatMessage, ConditionNode,
    EndNode, Flow, InputRequest, MockAction, SendMessageNode, SimulationState,
    SimulationStatus, WaitNode,
)

MAX_SIMULATION_STEPS = 50


class SimulationError(ValueError):
    pass


def start_simulation(flow: Flow) -> SimulationState:
    state = SimulationState(id=f"sim_{uuid4().hex[:12]}", flow_id=flow.id, current_node_id=flow.start_node_id)
    return run_until_pause(flow, state)


def reply_to_simulation(flow: Flow, state: SimulationState, value: Any) -> SimulationState:
    if state.status != SimulationStatus.WAITING_FOR_INPUT or not state.input_request:
        raise SimulationError("Simulation is not waiting for user input.")
    node = flow.node_map().get(state.current_node_id)
    if not isinstance(node, AskQuestionNode):
        raise SimulationError("Current simulation node is not a question.")
    normalized_value = value
    if node.options:
        option_map = {option.casefold(): option for option in node.options}
        matched = option_map.get(str(value).strip().casefold())
        if matched is None:
            raise SimulationError(f"Answer must be one of: {', '.join(node.options)}")
        normalized_value = matched
    state.messages.append(ChatMessage(sender="user", text=str(normalized_value)))
    state.variables[node.variable] = normalized_value
    state.current_node_id = node.next_node_id
    state.status = SimulationStatus.RUNNING
    state.input_request = None
    return run_until_pause(flow, state)


def run_until_pause(flow: Flow, state: SimulationState) -> SimulationState:
    node_map = flow.node_map()
    while state.status == SimulationStatus.RUNNING:
        if state.step_count >= MAX_SIMULATION_STEPS:
            return _fail(state, "Maximum simulation step limit exceeded.")
        node = node_map.get(state.current_node_id)
        if node is None:
            return _fail(state, f"Node '{state.current_node_id}' does not exist.")
        state.trace.append(node.id)
        state.step_count += 1

        if isinstance(node, SendMessageNode):
            state.messages.append(ChatMessage(sender="bot", text=_render(node.message, state.variables)))
            if not node.next_node_id:
                return _complete(state)
            state.current_node_id = node.next_node_id
        elif isinstance(node, AskQuestionNode):
            state.messages.append(ChatMessage(sender="bot", text=node.message))
            state.input_request = InputRequest(node_id=node.id, variable=node.variable, prompt=node.message, options=node.options)
            state.status = SimulationStatus.WAITING_FOR_INPUT
        elif isinstance(node, ConditionNode):
            actual = state.variables.get(node.variable)
            try:
                matched = evaluate_condition(actual, node.operator, node.value)
            except (TypeError, ValueError) as exc:
                return _fail(state, f"Condition '{node.id}' could not be evaluated: {exc}")
            target = node.true_node_id if matched else node.false_node_id
            state.actions.append(MockAction(type="condition_evaluated", node_id=node.id, detail=f"{node.variable} {node.operator} {node.value!r} -> {matched}", payload={"actual": actual, "matched": matched}))
            if not target:
                return _fail(state, f"Condition '{node.id}' has no matching path.")
            state.current_node_id = target
        elif isinstance(node, AssignTeamNode):
            state.actions.append(MockAction(type="assign_team", node_id=node.id, detail=f"Mock assigned conversation to {node.team_name}", payload={"team_name": node.team_name, "team_id": node.team_id}))
            if not node.next_node_id:
                return _complete(state)
            state.current_node_id = node.next_node_id
        elif isinstance(node, ApiCallNode):
            state.actions.append(MockAction(type="api_call", node_id=node.id, detail=f"Mocked {node.method} {node.url}", payload={"status": 200, "mocked": True}))
            if node.save_response_as:
                state.variables[node.save_response_as] = {"status": 200, "mocked": True}
            state.current_node_id = node.success_node_id
        elif isinstance(node, WaitNode):
            state.actions.append(MockAction(type="wait", node_id=node.id, detail=f"Fast-forwarded {node.duration_seconds} seconds", payload={"duration_seconds": node.duration_seconds}))
            state.current_node_id = node.next_node_id
        elif isinstance(node, EndNode):
            return _complete(state)
    return state


def evaluate_condition(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "equals":
        return _normalize(actual) == _normalize(expected)
    if operator == "not_equals":
        return _normalize(actual) != _normalize(expected)
    if operator == "contains":
        return str(expected).casefold() in str(actual or "").casefold()
    if operator == "greater_than":
        return float(actual) > float(expected)
    if operator == "less_than":
        return float(actual) < float(expected)
    raise SimulationError(f"Unsupported condition operator: {operator}")


def _normalize(value: Any) -> Any:
    return value.strip().casefold() if isinstance(value, str) else value


def _render(message: str, variables: dict[str, Any]) -> str:
    rendered = message
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", str(value)).replace("{{ " + key + " }}", str(value))
    return rendered


def _complete(state: SimulationState) -> SimulationState:
    state.status = SimulationStatus.COMPLETED
    state.input_request = None
    return state


def _fail(state: SimulationState, message: str) -> SimulationState:
    state.status = SimulationStatus.FAILED
    state.error = message
    state.input_request = None
    state.messages.append(ChatMessage(sender="system", text=message))
    return state
