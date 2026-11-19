from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from app.domain.models import Flow
from app.services.rules import UnsupportedIntentError, generate_rule_flow

load_dotenv()


SYSTEM_PROMPT = """You are a workflow compiler for Wati-style chatbot automations.
Convert the user's natural-language requirement into a Flow JSON object matching the supplied JSON schema.

Rules:
1. Output JSON only. Do not use Markdown fences.
2. Use only supported node types.
3. Never invent real team IDs, credentials, secrets, or customer data.
4. Use null placeholders when deployment configuration is missing.
5. Every node reference must point to an existing node.
6. Every flow must have a reachable end node.
7. Collect a variable before using it in a condition.
8. Include a false/fallback path for every condition.
9. Do not execute API calls; describe them in the flow only.
10. Keep the flow as small as possible while preserving the user's intent.
"""


@dataclass
class GenerationResult:
    flow: Flow
    mode: str
    notices: list[str] = field(default_factory=list)


class GenerationUnavailableError(RuntimeError):
    pass


def generate_flow(requirement: str) -> GenerationResult:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

    if not api_key:
        return GenerationResult(
            flow=generate_rule_flow(requirement),
            mode="offline_rules",
            notices=["No DeepSeek API key configured; used the supported offline rules."],
        )

    try:
        content = _call_openai_compatible(api_key, base_url, model, requirement)
        return GenerationResult(flow=Flow.model_validate(_extract_json(content)), mode="llm")
    except Exception as exc:
        try:
            flow = generate_rule_flow(requirement)
        except UnsupportedIntentError as rule_exc:
            raise GenerationUnavailableError(
                "DeepSeek generation failed and offline rules do not support this requirement. "
                "Check your API configuration and try again."
            ) from exc
        return GenerationResult(flow=flow, mode="offline_rules", notices=[
            "DeepSeek generation failed; used the supported offline rules."
        ])


def _call_openai_compatible(api_key: str, base_url: str, model: str, requirement: str) -> str:
    schema = json.dumps(Flow.model_json_schema(), ensure_ascii=False)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + "\nJSON schema:\n" + schema},
            {"role": "user", "content": requirement},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=35) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"provider returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"could not connect to provider: {exc.reason}") from exc
    return body["choices"][0]["message"]["content"]


def _extract_json(content: str) -> dict:
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _heuristic_flow(requirement: str) -> Flow:
    """Compatibility wrapper for callers using the previous helper name."""
    return generate_rule_flow(requirement)
