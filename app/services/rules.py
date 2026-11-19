"""Small, explicit grammar for the no-key demo. Unsupported intent must fail closed."""

from __future__ import annotations

import re
from uuid import uuid4

from app.domain.models import Flow


class UnsupportedIntentError(ValueError):
    pass


def generate_rule_flow(requirement: str) -> Flow:
    text = " ".join(requirement.strip().split())
    trigger = _trigger(text)
    lowered = text.casefold()

    if re.search(r"\bbuyers?\b", text, re.I) and re.search(r"\bsellers?\b", text, re.I):
        return _buyer_seller(text, trigger)
    if re.search(r"\b(?:employee|company size|enterprise)\b", text, re.I):
        return _qualification(text, trigger)
    if "url" in lowered or "api" in lowered or "webhook" in lowered:
        return _risky_api(text, trigger)
    if re.search(r"\b(?:assign|route)\b", text, re.I):
        return _assignment(text, trigger)

    raise UnsupportedIntentError(
        "No-key mode supports buyer/seller routing, employee-count qualification, "
        "keyword-triggered team assignment, and the customer URL safety example. "
        "Add a DeepSeek API key for other requirements."
    )


def _trigger(text: str) -> dict:
    if re.search(r"\bwhen\s+(?:a\s+)?new\s+lead\s+asks\s+(?:for|about)\s+pricing\b", text, re.I):
        return {"type": "pricing_question", "description": "A new lead asks for pricing", "config": {}}
    if re.search(r"\bwhen\s+(?:a\s+)?new\s+contact\s+(?:messages\s+us|sends\s+(?:us\s+)?a\s+message)\b", text, re.I):
        return {"type": "new_contact_message", "description": "A new contact sends a message", "config": {}}
    keyword = re.search(r"\bwhen\s+(?:someone|a\s+(?:customer|contact))\s+(?:types|sends\s+a)\s+([\w-]+)(?:\s+message)?\b", text, re.I)
    if keyword:
        word = keyword.group(1).casefold()
        return {"type": "keyword_message", "description": f"A contact sends a message containing '{word}'", "config": {"keyword": word}}
    raise UnsupportedIntentError(
        "No-key mode needs a supported trigger: 'When a new contact messages us', "
        "'When a new lead asks for pricing', or 'When someone types refund'."
    )


def _team(text: str, subject: str) -> str:
    match = re.search(
        rf"\b(?:assign|route)\s+{subject}\s+to\s+([A-Za-z][A-Za-z ]{{0,40}}?)"
        rf"(?=\s*(?:[.,;]|\band\s+(?:send|assign|route|wait)\b|\botherwise\b|$))",
        text,
        re.I,
    )
    if not match:
        raise UnsupportedIntentError("Specify the target team with 'assign them to TEAM' or 'route buyers to TEAM'.")
    return match.group(1).strip()


def _wait_seconds(text: str) -> int | None:
    if re.search(r"\bafter\s+\d+\s*(?:seconds?|minutes?|hours?)\b", text, re.I):
        raise UnsupportedIntentError("Use 'wait N minutes' for timing in no-key mode.")
    matches = list(re.finditer(r"\bwait\s+(\d+)\s*(seconds?|minutes?|hours?)\b", text, re.I))
    if len(matches) > 1 or (re.search(r"\bwait\b", text, re.I) and not matches):
        raise UnsupportedIntentError("Specify exactly one wait, such as 'wait 5 minutes'.")
    if not matches:
        return None
    count, unit = matches[0].groups()
    seconds = int(count) * (3600 if unit.lower().startswith("hour") else 60 if unit.lower().startswith("minute") else 1)
    if seconds <= 0:
        raise UnsupportedIntentError("Wait duration must be positive.")
    return seconds


def _flow(name: str, description: str, trigger: dict, start: str, nodes: list[dict]) -> Flow:
    return Flow.model_validate({
        "id": f"flow_{uuid4().hex[:10]}", "name": name, "description": description,
        "trigger": trigger, "start_node_id": start, "nodes": nodes,
    })


def _buyer_seller(text: str, trigger: dict) -> Flow:
    if trigger["type"] != "new_contact_message":
        raise UnsupportedIntentError("Buyer/seller routing supports the new-contact trigger in no-key mode.")
    if _wait_seconds(text) is not None or re.search(r"\b(?:api|webhook|url|employee)\b", text, re.I):
        raise UnsupportedIntentError("Buyer/seller routing with extra timing, API calls, or conditions needs a model.")
    if re.search(r"\b(?:route|assign)\s+sellers?\b|\b(?:email|notify)\b", text, re.I):
        raise UnsupportedIntentError("The seller branch supports sending a help article only.")
    if not re.search(r"\bask\b.*\bbuyers?\s+or\s+(?:a\s+)?sellers?\b", text, re.I):
        raise UnsupportedIntentError("Ask whether the contact is a buyer or seller.")
    if not re.search(r"\bsend\b.*\bsellers?\b.*\bhelp\s+article\b", text, re.I):
        raise UnsupportedIntentError("Specify sending the help article to sellers.")
    sales_team = _team(text, r"buyers?")
    return _flow("Buyer and seller routing", "Ask the contact's role and route each answer.", trigger, "ask_role", [
        {"id": "ask_role", "type": "ask_question", "message": "Are you a buyer or a seller?", "variable": "contact_role", "options": ["Buyer", "Seller"], "next_node_id": "check_role"},
        {"id": "check_role", "type": "condition", "variable": "contact_role", "operator": "equals", "value": "Buyer", "true_node_id": "assign_sales", "false_node_id": "send_help"},
        {"id": "assign_sales", "type": "assign_team", "team_name": sales_team, "team_id": None, "next_node_id": "buyer_end"},
        {"id": "send_help", "type": "send_message", "message": "Here is our seller help article: {{seller_help_url}}", "next_node_id": "seller_end"},
        {"id": "buyer_end", "type": "end"}, {"id": "seller_end", "type": "end"},
    ])


def _qualification(text: str, trigger: dict) -> Flow:
    if trigger["type"] != "pricing_question":
        raise UnsupportedIntentError("Employee-count qualification supports the pricing-question trigger in no-key mode.")
    threshold = re.search(r"\bmore\s+than\s+(\d+)\s+employees\b", text, re.I)
    if not threshold or not re.search(r"\b(?:ask|collect)\b.*\b(?:company size|employees?)\b", text, re.I):
        raise UnsupportedIntentError("Ask for company size and specify 'more than N employees'.")
    if not re.search(r"\botherwise\b.*\bsend\b.*\bpricing\s+page\b", text, re.I):
        raise UnsupportedIntentError("Specify the otherwise branch sending the pricing page.")
    if re.search(r"\b(?:api|webhook|email|notify)\b", text, re.I):
        raise UnsupportedIntentError("API calls in lead qualification need a model.")
    team = _team(text, r"(?:them|the\s+(?:chat|conversation))")
    seconds = _wait_seconds(text)
    nodes = [
        {"id": "ask_size", "type": "ask_question", "message": "How many employees does your company have?", "variable": "employee_count", "options": [], "next_node_id": "check_size"},
        {"id": "check_size", "type": "condition", "variable": "employee_count", "operator": "greater_than", "value": int(threshold.group(1)), "true_node_id": "wait_for_sales" if seconds else "assign_enterprise", "false_node_id": "send_pricing"},
    ]
    if seconds:
        nodes.append({"id": "wait_for_sales", "type": "wait", "duration_seconds": seconds, "next_node_id": "assign_enterprise"})
    nodes.extend([
        {"id": "assign_enterprise", "type": "assign_team", "team_name": team, "team_id": None, "next_node_id": "enterprise_end"},
        {"id": "send_pricing", "type": "send_message", "message": "You can view our self-service pricing at {{pricing_url}}", "next_node_id": "standard_end"},
        {"id": "enterprise_end", "type": "end"}, {"id": "standard_end", "type": "end"},
    ])
    return _flow("Lead qualification", "Route leads using an employee-count threshold.", trigger, "ask_size", nodes)


def _assignment(text: str, trigger: dict) -> Flow:
    if trigger["type"] != "keyword_message":
        raise UnsupportedIntentError("Simple team assignment needs a keyword trigger, such as 'When someone types refund'.")
    if re.search(r"\b(?:ask|if|otherwise|send|email|notify|api|webhook)\b", text, re.I):
        raise UnsupportedIntentError("This rule supports a wait and team assignment only; other actions need a model.")
    team = _team(text, r"(?:them|the\s+(?:chat|conversation))")
    seconds = _wait_seconds(text)
    nodes: list[dict] = []
    if seconds:
        nodes.append({"id": "delay", "type": "wait", "duration_seconds": seconds, "next_node_id": "assign_team"})
    nodes.extend([
        {"id": "assign_team", "type": "assign_team", "team_name": team, "team_id": None, "next_node_id": "end"},
        {"id": "end", "type": "end"},
    ])
    return _flow("Keyword-based team assignment", "Assign a message to a team after an optional wait.", trigger, "delay" if seconds else "assign_team", nodes)


def _risky_api(text: str, trigger: dict) -> Flow:
    if trigger["type"] != "new_contact_message":
        raise UnsupportedIntentError("The customer URL safety example needs a new-contact trigger.")
    if not re.search(r"\bask\b.*\b(?:customer|contact)\b.*\burl\b.*\bcall\b.*\b(?:that|the)\s+url\b", text, re.I):
        raise UnsupportedIntentError("No-key API example supports asking for a customer URL and calling that URL.")
    team = _team(text, r"(?:them|the\s+(?:chat|conversation))")
    return _flow("Customer-provided API workflow", "Review an unsafe customer-provided API destination.", trigger, "ask_url", [
        {"id": "ask_url", "type": "ask_question", "message": "Which URL should we call?", "variable": "customer_url", "options": [], "next_node_id": "call_api"},
        {"id": "call_api", "type": "api_call", "method": "POST", "url": "https://{{customer_url}}", "request_body": {"contact": "{{contact}}"}, "save_response_as": "api_response", "success_node_id": "assign_support", "failure_node_id": None},
        {"id": "assign_support", "type": "assign_team", "team_name": team, "team_id": None, "next_node_id": "end"},
        {"id": "end", "type": "end"},
    ])
