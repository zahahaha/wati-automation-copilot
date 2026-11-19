from app.domain.models import SimulationStatus
from app.domain.simulator import reply_to_simulation, start_simulation
from tests.fixtures import buyer_seller_flow


def test_buyer_is_assigned_to_sales() -> None:
    flow = buyer_seller_flow()
    state = start_simulation(flow)
    assert state.status == SimulationStatus.WAITING_FOR_INPUT

    state = reply_to_simulation(flow, state, "buyer")
    assert state.status == SimulationStatus.COMPLETED
    assert any(action.type == "assign_team" for action in state.actions)
    assert state.trace == ["ask_role", "check_role", "assign_sales", "buyer_end"]


def test_seller_receives_help_article() -> None:
    flow = buyer_seller_flow()
    state = reply_to_simulation(flow, start_simulation(flow), "Seller")
    assert state.status == SimulationStatus.COMPLETED
    assert state.messages[-1].text == "Help article"
    assert state.trace == ["ask_role", "check_role", "send_help", "seller_end"]


def test_invalid_option_is_rejected() -> None:
    flow = buyer_seller_flow()
    state = start_simulation(flow)
    try:
        reply_to_simulation(flow, state, "Other")
    except ValueError as exc:
        assert "Buyer, Seller" in str(exc)
    else:
        raise AssertionError("Expected invalid option to be rejected")
