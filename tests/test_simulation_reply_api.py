from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException

from app import main
from app.main import ReplyRequest
from app.repositories import InMemoryRepository
from app.domain.simulator import start_simulation
from tests.fixtures import buyer_seller_flow


def test_duplicate_reply_advances_only_once(monkeypatch) -> None:
    repo = InMemoryRepository()
    monkeypatch.setattr(main, "repository", repo)
    flow = buyer_seller_flow()
    repo.save_flow(flow)
    initial = repo.save_simulation(start_simulation(flow))
    assert initial.version == 0

    ready = Barrier(3)

    def submit() -> tuple[int, object]:
        ready.wait()
        try:
            return 200, main.reply(initial.id, ReplyRequest(value="Buyer", expected_version=0))
        except HTTPException as exc:
            return exc.status_code, exc.detail

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(submit)
        second = pool.submit(submit)
        ready.wait()
        results = [first.result(), second.result()]

    assert sorted(status for status, _ in results) == [200, 409]
    state = repo.get_simulation(initial.id)
    assert state.version == 1
    assert state.trace == ["ask_role", "check_role", "assign_sales", "buyer_end"]
    assert [action.payload["team_name"] for action in state.actions if action.type == "assign_team"] == ["Sales"]
    assert [message.text for message in state.messages if message.sender == "user"] == ["Buyer"]


def test_invalid_reply_does_not_change_stored_session(monkeypatch) -> None:
    repo = InMemoryRepository()
    monkeypatch.setattr(main, "repository", repo)
    flow = buyer_seller_flow()
    repo.save_flow(flow)
    initial = repo.save_simulation(start_simulation(flow))

    try:
        main.reply(initial.id, ReplyRequest(value="Other", expected_version=0))
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Expected invalid reply to be rejected")
    state = repo.get_simulation(initial.id)
    assert state.version == 0
    assert state.trace == ["ask_role"]
