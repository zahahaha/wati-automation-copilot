from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.domain.models import Flow
from app.domain.simulator import SimulationError, start_simulation
from app.domain.validator import validate_flow
from app.repositories import StaleSimulationError, repository
from app.services.explainer import explain_flow
from app.services.generator import GenerationUnavailableError, generate_flow
from app.services.rules import UnsupportedIntentError


class GenerateFlowRequest(BaseModel):
    requirement: str = Field(min_length=10, max_length=5_000)


class ReplyRequest(BaseModel):
    value: Any
    expected_version: int = Field(ge=0)


app = FastAPI(
    title="Wati Automation Copilot",
    description="Generate, validate, explain, and simulate Wati-style chatbot workflows.",
    version="0.1.0",
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/flows/generate")
def create_flow(request: GenerateFlowRequest) -> dict:
    try:
        result = generate_flow(request.requirement)
    except UnsupportedIntentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GenerationUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    repository.save_flow(result.flow)
    review = validate_flow(result.flow)
    return {
        "flow": result.flow,
        "explanation": explain_flow(result.flow),
        "review": review,
        "generation_mode": result.mode,
        "notices": result.notices,
    }


@app.get("/api/flows/{flow_id}")
def get_flow(flow_id: str) -> Flow:
    flow = repository.get_flow(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@app.post("/api/flows/{flow_id}/validate")
def review_flow(flow_id: str):
    flow = repository.get_flow(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return validate_flow(flow)


@app.post("/api/flows/{flow_id}/simulations")
def create_simulation(flow_id: str):
    flow = repository.get_flow(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    review = validate_flow(flow)
    if not review.valid:
        raise HTTPException(status_code=422, detail={"message": "Flow contains blocking validation errors", "review": review.model_dump(mode="json")})
    state = start_simulation(flow)
    return repository.save_simulation(state)


@app.post("/api/simulations/{simulation_id}/reply")
def reply(simulation_id: str, request: ReplyRequest):
    try:
        updated = repository.reply_to_simulation(simulation_id, request.expected_version, request.value)
    except (SimulationError, StaleSimulationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return updated
