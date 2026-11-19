from app.domain.models import Flow
from app.domain.validator import validate_flow
from tests.fixtures import buyer_seller_flow


def test_valid_flow_has_no_errors() -> None:
    result = validate_flow(buyer_seller_flow())
    assert result.valid is True
    assert result.errors == []


def test_broken_reference_is_an_error() -> None:
    flow = buyer_seller_flow()
    flow.nodes[0].next_node_id = "missing_node"
    result = validate_flow(flow)
    assert result.valid is False
    assert "BROKEN_REFERENCE" in {issue.code for issue in result.errors}


def test_dynamic_api_target_is_blocking() -> None:
    flow = Flow.model_validate(
        {
            "id": "api_flow",
            "name": "Unsafe API",
            "description": "Unsafe dynamic host",
            "trigger": {"type": "message", "description": "a message arrives", "config": {}},
            "start_node_id": "ask",
            "nodes": [
                {"id": "ask", "type": "ask_question", "message": "URL?", "variable": "url", "options": [], "next_node_id": "api"},
                {"id": "api", "type": "api_call", "method": "POST", "url": "https://{{url}}", "request_body": {}, "success_node_id": "end", "failure_node_id": None},
                {"id": "end", "type": "end"},
            ],
        }
    )
    result = validate_flow(flow)
    assert result.valid is False
    assert "DYNAMIC_API_URL" in {issue.code for issue in result.errors}
    assert "MISSING_API_FAILURE_PATH" in {issue.code for issue in result.warnings}


def test_cycle_is_reported() -> None:
    flow = buyer_seller_flow()
    flow.nodes[-1] = Flow.model_validate(
        {
            "id": "temp",
            "name": "temp",
            "description": "temp",
            "trigger": {"type": "message", "description": "message", "config": {}},
            "start_node_id": "loop",
            "nodes": [{"id": "loop", "type": "send_message", "message": "again", "next_node_id": "loop"}],
        }
    ).nodes[0]
    # Put an isolated cycle in the graph; it is reported as unreachable rather than a reachable cycle.
    result = validate_flow(flow)
    assert "UNREACHABLE_NODE" in {issue.code for issue in result.warnings}


def test_condition_requires_value_before_it_on_every_path() -> None:
    flow = Flow.model_validate({
        "id": "early_condition", "name": "Early condition", "description": "Wrong order",
        "trigger": {"type": "message", "description": "a message arrives"},
        "start_node_id": "check",
        "nodes": [
            {"id": "check", "type": "condition", "variable": "role", "operator": "equals", "value": "Buyer", "true_node_id": "ask", "false_node_id": "end"},
            {"id": "ask", "type": "ask_question", "message": "Role?", "variable": "role", "next_node_id": "end"},
            {"id": "end", "type": "end"},
        ],
    })
    result = validate_flow(flow)
    assert not result.valid
    assert "VARIABLE_NOT_ON_ALL_PATHS" in {issue.code for issue in result.errors}


def test_reachable_loop_is_blocking_even_if_another_branch_ends() -> None:
    flow = buyer_seller_flow()
    flow.nodes.append(Flow.model_validate({
        "id": "loop_flow", "name": "loop", "description": "loop",
        "trigger": {"type": "message", "description": "a message arrives"},
        "start_node_id": "loop", "nodes": [{"id": "loop", "type": "send_message", "message": "again", "next_node_id": "loop"}],
    }).nodes[0])
    flow.node_map()["check_role"].false_node_id = "loop"
    result = validate_flow(flow)
    assert not result.valid
    assert "CYCLE_DETECTED" in {issue.code for issue in result.errors}
