from __future__ import annotations

from threading import RLock

from app.domain.models import Flow, SimulationState
from app.domain.simulator import reply_to_simulation


class StaleSimulationError(ValueError):
    pass


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

    def reply_to_simulation(self, simulation_id: str, expected_version: int, value: object) -> SimulationState | None:
        with self._lock:
            state = self._simulations.get(simulation_id)
            if state is None:
                return None
            if state.version != expected_version:
                raise StaleSimulationError("Simulation has changed. Refresh the conversation before replying again.")
            flow = self._flows.get(state.flow_id)
            if flow is None:
                raise LookupError("Flow not found")
            # Work on a copy so a rejected reply cannot change the stored state.
            updated = reply_to_simulation(flow, state.model_copy(deep=True), value)
            updated.version = state.version + 1
            self._simulations[simulation_id] = updated
            return updated


repository = InMemoryRepository()
