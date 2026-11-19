from __future__ import annotations

import re
from collections import Counter, deque

from app.domain.models import (
    ApiCallNode,
    AskQuestionNode,
    AssignTeamNode,
    ConditionNode,
    Flow,
    IssueSeverity,
    SendMessageNode,
    ValidationIssue,
    ValidationResult,
    WaitNode,
)


def outgoing_node_ids(node: object) -> list[str]:
    if isinstance(node, ConditionNode):
        return [value for value in (node.true_node_id, node.false_node_id) if value]
    if isinstance(node, ApiCallNode):
        return [value for value in (node.success_node_id, node.failure_node_id) if value]
    next_node_id = getattr(node, "next_node_id", None)
    return [next_node_id] if next_node_id else []


def validate_flow(flow: Flow) -> ValidationResult:
    issues: list[ValidationIssue] = []
    ids = [node.id for node in flow.nodes]

    for node_id, count in Counter(ids).items():
        if count > 1:
            issues.append(_issue("error", "DUPLICATE_NODE_ID", f"Node ID '{node_id}' appears {count} times.", node_id, "Give every node a unique ID."))

    node_map = flow.node_map()
    if flow.start_node_id not in node_map:
        issues.append(_issue("error", "MISSING_START_NODE", f"Start node '{flow.start_node_id}' does not exist.", suggestion="Select an existing node as the start node."))

    for node in flow.nodes:
        for target_id in outgoing_node_ids(node):
            if target_id not in node_map:
                issues.append(_issue("error", "BROKEN_REFERENCE", f"Node '{node.id}' points to missing node '{target_id}'.", node.id, "Connect it to an existing node."))

    reachable = _reachable_ids(flow, node_map)
    for node_id in ids:
        if node_id not in reachable:
            issues.append(_issue("warning", "UNREACHABLE_NODE", f"Node '{node_id}' cannot be reached from the start node.", node_id, "Connect or remove this node."))

    if flow.start_node_id in node_map and not any(node.type == "end" and node.id in reachable for node in flow.nodes):
        issues.append(_issue("error", "NO_REACHABLE_END", "No end node is reachable from the start node.", suggestion="Ensure at least one execution path terminates."))

    cycle = _find_cycle(flow, node_map)
    if cycle:
        issues.append(_issue("error", "CYCLE_DETECTED", f"The flow contains a reachable cycle involving '{cycle}'.", cycle, "Remove the cycle before simulation."))

    asked_variables = {node.variable for node in flow.nodes if isinstance(node, AskQuestionNode)}
    defined_before = _variables_before_each_node(flow, node_map)
    for node in flow.nodes:
        if isinstance(node, ConditionNode):
            if node.variable not in asked_variables:
                issues.append(_issue("error", "UNDEFINED_VARIABLE", f"Condition uses variable '{node.variable}' that is never collected.", node.id, "Add an Ask Question node that stores this variable."))
            elif node.id in defined_before and node.variable not in defined_before[node.id]:
                issues.append(_issue("error", "VARIABLE_NOT_ON_ALL_PATHS", f"Condition uses '{node.variable}' before it is collected on every path.", node.id, "Move the question before the condition on every path."))
            if not node.false_node_id:
                issues.append(_issue("warning", "MISSING_FALSE_PATH", "Condition has no false/default path.", node.id, "Add a fallback path for unexpected answers."))

        if isinstance(node, AskQuestionNode) and not node.options:
            issues.append(_issue("info", "FREE_TEXT_INPUT", "Question accepts free-text input.", node.id, "Consider adding options or input validation."))

        if isinstance(node, AssignTeamNode) and not node.team_id:
            issues.append(_issue("warning", "UNRESOLVED_TEAM", f"Team '{node.team_name}' has no concrete Wati team ID.", node.id, "Select an existing team before publishing."))

        if isinstance(node, ApiCallNode):
            if not node.failure_node_id:
                issues.append(_issue("warning", "MISSING_API_FAILURE_PATH", "API call has no failure path.", node.id, "Add a timeout/error branch."))
            if "{{" in node.url or "}}" in node.url:
                issues.append(_issue("error", "DYNAMIC_API_URL", "API target is controlled by a runtime variable and may allow SSRF.", node.id, "Use an allow-listed host and interpolate only path/query values."))
            if node.url.startswith("http://"):
                issues.append(_issue("warning", "INSECURE_API_URL", "API call uses unencrypted HTTP.", node.id, "Use HTTPS for external calls."))

        if isinstance(node, WaitNode) and node.duration_seconds > 86_400:
            issues.append(_issue("warning", "LONG_WAIT", "Wait duration is longer than 24 hours.", node.id, "Confirm that the long delay is intentional."))

        if isinstance(node, SendMessageNode):
            for variable in re.findall(r"{{\s*([a-zA-Z_][\w.]*)\s*}}", node.message):
                if variable not in asked_variables:
                    issues.append(_issue("warning", "UNKNOWN_TEMPLATE_VARIABLE", f"Message references unknown variable '{variable}'.", node.id, "Collect the value before using it in a message."))
                elif node.id in defined_before and variable not in defined_before[node.id]:
                    issues.append(_issue("warning", "TEMPLATE_VARIABLE_NOT_ON_ALL_PATHS", f"Message uses '{variable}' before it is collected on every path.", node.id, "Collect the value on each path before sending this message."))

    errors = [item for item in issues if item.severity.value == "error"]
    warnings = [item for item in issues if item.severity.value == "warning"]
    info = [item for item in issues if item.severity.value == "info"]
    return ValidationResult(valid=not errors, errors=errors, warnings=warnings, info=info)


def _reachable_ids(flow: Flow, node_map: dict[str, object]) -> set[str]:
    if flow.start_node_id not in node_map:
        return set()
    seen: set[str] = set()
    queue: deque[str] = deque([flow.start_node_id])
    while queue:
        node_id = queue.popleft()
        if node_id in seen or node_id not in node_map:
            continue
        seen.add(node_id)
        queue.extend(outgoing_node_ids(node_map[node_id]))
    return seen


def _variables_before_each_node(flow: Flow, node_map: dict[str, object]) -> dict[str, set[str]]:
    """Variables guaranteed to exist at a node, intersected across incoming paths."""
    if flow.start_node_id not in node_map:
        return {}
    incoming: dict[str, set[str]] = {flow.start_node_id: set()}
    queue: deque[str] = deque([flow.start_node_id])
    while queue:
        node_id = queue.popleft()
        node = node_map[node_id]
        outgoing = outgoing_node_ids(node)
        for target in outgoing:
            if target not in node_map:
                continue
            values = incoming[node_id].copy()
            if isinstance(node, AskQuestionNode):
                values.add(node.variable)
            if isinstance(node, ApiCallNode) and target == node.success_node_id and node.save_response_as:
                values.add(node.save_response_as)
            merged = incoming[target] & values if target in incoming else values
            if target not in incoming or incoming[target] != merged:
                incoming[target] = merged
                queue.append(target)
    return incoming


def _find_cycle(flow: Flow, node_map: dict[str, object]) -> str | None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> str | None:
        if node_id in visiting:
            return node_id
        if node_id in visited or node_id not in node_map:
            return None
        visiting.add(node_id)
        for target in outgoing_node_ids(node_map[node_id]):
            found = visit(target)
            if found:
                return found
        visiting.remove(node_id)
        visited.add(node_id)
        return None

    return visit(flow.start_node_id)


def _issue(severity: str, code: str, message: str, node_id: str | None = None, suggestion: str | None = None) -> ValidationIssue:
    return ValidationIssue(severity=severity, code=code, message=message, node_id=node_id, suggestion=suggestion)
