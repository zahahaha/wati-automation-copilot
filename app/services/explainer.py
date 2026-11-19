from app.domain.models import (
    ApiCallNode, AskQuestionNode, AssignTeamNode, ConditionNode, EndNode,
    Flow, SendMessageNode, WaitNode,
)


def explain_flow(flow: Flow) -> list[str]:
    lines = [f"The automation starts when {flow.trigger.description.lower()}."]
    for node in flow.nodes:
        if isinstance(node, AskQuestionNode):
            suffix = f" Suggested answers: {', '.join(node.options)}." if node.options else ""
            lines.append(f"It asks: “{node.message}” and stores the answer as {node.variable}.{suffix}")
        elif isinstance(node, ConditionNode):
            lines.append(f"It checks whether {node.variable} {node.operator.replace('_', ' ')} {node.value!r}, then follows the matching branch.")
        elif isinstance(node, SendMessageNode):
            lines.append(f"It sends the message: “{node.message}”")
        elif isinstance(node, AssignTeamNode):
            lines.append(f"It assigns the conversation to the {node.team_name} team.")
        elif isinstance(node, WaitNode):
            lines.append(f"It waits {node.duration_seconds} seconds before continuing.")
        elif isinstance(node, ApiCallNode):
            lines.append(f"It performs a mocked {node.method} request to {node.url}; no real network call is made during simulation.")
        elif isinstance(node, EndNode):
            lines.append("That branch then ends.")
    return lines
