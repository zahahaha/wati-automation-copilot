from __future__ import annotations

from threading import RLock

from app.domain.models import Flow, SimulationState


class InMemoryRepository:
    def __init__(self) -> None:
        self._flows: dict[str, Flow] = {}
        self._simulations: dict[str, SimulationState] = {}
        self._lock = RLock()

    def save_flow(self, flow: Flow) -> Flow:
        with self._lock:
            self._flows[flow.id] = flow
        return flow

    def get_flow(self, flow_id: str) -> Flow | None:
        with self._lock:
            return self._flows.get(flow_id)

    def save_simulation(self, simulation: SimulationState) -> SimulationState:
        with self._lock:
            self._simulations[simulation.id] = simulation
        return simulation

    def get_simulation(self, simulation_id: str) -> SimulationState | None:
        with self._lock:
            return self._simulations.get(simulation_id)


repository = InMemoryRepository()
