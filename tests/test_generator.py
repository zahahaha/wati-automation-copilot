import pytest
from fastapi import HTTPException

from app.domain.validator import validate_flow
from app.main import GenerateFlowRequest, create_flow
from app.services.generator import generate_flow
from app.services.rules import UnsupportedIntentError


ROUTING = "When a new contact messages us, ask if they are a buyer or seller, then route buyers to Sales and send sellers our help article."
QUALIFICATION = "When a new lead asks for pricing, collect their company size. If they have more than 75 employees, wait 10 minutes and assign them to Priority Sales. Otherwise, send the self-service pricing page."
RISKY = "When a new contact messages us, ask the customer for a URL and call that URL with their contact information. If the API succeeds, assign them to Support."


def test_demo_generator_builds_buyer_seller_flow(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    result = generate_flow(ROUTING)
    assert result.mode == "offline_rules"
    assert result.flow.start_node_id == "ask_role"
    assert {node.type for node in result.flow.nodes} >= {"ask_question", "condition", "assign_team"}


def test_demo_generator_builds_risky_flow_for_review(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    result = generate_flow(RISKY)
    api_node = next(node for node in result.flow.nodes if node.type == "api_call")
    assert "{{customer_url}}" in api_node.url


def test_deepseek_configuration_is_used(monkeypatch) -> None:
    from app.services import generator

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    expected = generator._heuristic_flow(ROUTING)
    calls = []

    def fake_call(api_key, base_url, model, requirement):
        calls.append((api_key, base_url, model, requirement))
        return expected.model_dump_json()

    monkeypatch.setattr(generator, "_call_openai_compatible", fake_call)
    result = generator.generate_flow("Route buyer and seller")
    assert result.mode == "llm"
    assert calls == [("test-key", "https://api.deepseek.com", "deepseek-flash", "Route buyer and seller")]


def test_qualification_extracts_threshold_wait_and_team(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    flow = generate_flow(QUALIFICATION).flow
    nodes = flow.node_map()
    assert nodes["check_size"].value == 75
    assert nodes["wait_for_sales"].duration_seconds == 600
    assert nodes["assign_enterprise"].team_name == "Priority Sales"
    assert validate_flow(flow).valid


def test_keyword_wait_assignment_preserves_intent(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    flow = generate_flow("When someone types refund, wait 2 hours and assign the chat to Billing.").flow
    assert flow.trigger.config == {"keyword": "refund"}
    assert flow.node_map()["delay"].duration_seconds == 7200
    assert flow.node_map()["assign_team"].team_name == "Billing"


def test_unsupported_request_returns_422_instead_of_unrelated_flow(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    with pytest.raises(UnsupportedIntentError):
        generate_flow("When someone types refund, send a discount coupon.")
    with pytest.raises(HTTPException) as error:
        create_flow(GenerateFlowRequest(requirement="When someone types refund, send a discount coupon."))
    assert error.value.status_code == 422


def test_provider_failure_does_not_hide_unsupported_intent(monkeypatch) -> None:
    from app.services import generator

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(generator, "_call_openai_compatible", lambda *args: (_ for _ in ()).throw(RuntimeError("provider down")))
    with pytest.raises(generator.GenerationUnavailableError):
        generate_flow("When someone types refund, send a discount coupon.")
    assert generate_flow(ROUTING).mode == "offline_rules"


def test_offline_rules_reject_extra_actions_instead_of_dropping_them(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    with pytest.raises(UnsupportedIntentError):
        generate_flow("When someone types refund, wait 2 hours and assign the chat to Billing and email the manager.")
    with pytest.raises(UnsupportedIntentError):
        generate_flow("When a new contact messages us, ask if they are a buyer or seller, route buyers to Sales and send sellers our help article after 2 hours.")
