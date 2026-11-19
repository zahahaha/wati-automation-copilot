from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Trigger(BaseModel):
    type: str = "new_contact_message"
    description: str = "A new contact sends a message"
    config: dict[str, Any] = Field(default_factory=dict)


class SendMessageNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["send_message"]
    message: str
    next_node_id: str | None = None


class AskQuestionNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["ask_question"]
    message: str
    variable: str
    options: list[str] = Field(default_factory=list)
    next_node_id: str


class ConditionNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["condition"]
    variable: str
    operator: Literal[
        "equals", "not_equals", "contains", "greater_than", "less_than"
    ]
    value: str | int | float | bool
    true_node_id: str
    false_node_id: str | None = None


class AssignTeamNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["assign_team"]
    team_name: str
    team_id: str | None = None
    next_node_id: str | None = None


class WaitNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["wait"]
    duration_seconds: int = Field(gt=0)
    next_node_id: str


class ApiCallNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["api_call"]
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    url: str
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    request_body: dict[str, Any] = Field(default_factory=dict)
    save_response_as: str | None = None
    success_node_id: str
    failure_node_id: str | None = None

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        if value.startswith(("http://", "https://")):
            return value
        raise ValueError("API URL must start with http:// or https://")


class EndNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["end"]


Node = Annotated[
    Union[
        SendMessageNode,
        AskQuestionNode,
        ConditionNode,
        AssignTeamNode,
        WaitNode,
        ApiCallNode,
        EndNode,
    ],
    Field(discriminator="type"),
]


class Flow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str
    trigger: Trigger
    start_node_id: str
    nodes: list[Node] = Field(min_length=1, max_length=50)

    def node_map(self) -> dict[str, Node]:
        return {node.id: node for node in self.nodes}


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    severity: IssueSeverity
    code: str
    message: str
    node_id: str | None = None
    suggestion: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    info: list[ValidationIssue] = Field(default_factory=list)


class SimulationStatus(str, Enum):
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatMessage(BaseModel):
    sender: Literal["bot", "user", "system"]
    text: str


class MockAction(BaseModel):
    type: str
    node_id: str
    detail: str
    payload: dict[str, Any] = Field(default_factory=dict)


class InputRequest(BaseModel):
    node_id: str
    variable: str
    prompt: str
    options: list[str] = Field(default_factory=list)


class SimulationState(BaseModel):
    id: str
    flow_id: str
    current_node_id: str
    variables: dict[str, Any] = Field(default_factory=dict)
    messages: list[ChatMessage] = Field(default_factory=list)
    actions: list[MockAction] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    step_count: int = 0
    status: SimulationStatus = SimulationStatus.RUNNING
    error: str | None = None
    input_request: InputRequest | None = None
