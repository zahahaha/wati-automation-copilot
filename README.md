# Wati Automation Copilot

A lightweight AI-assisted automation builder that converts plain-English intent into a structured Wati-style chatbot flow, explains and validates the flow, and runs a safe mock conversation before publishing.

## Submission at a glance

- [One-page design and AI collaboration write-up](docs/write-up.md)
- [3�C5 minute recording script](docs/demo-script.md)
- Demo recording: **pending recording/upload**. Add its URL here before sending the submission; the script is not a recording.

## Why this design

The LLM is treated as a **workflow compiler, not the runtime**. It translates intent into a constrained `Flow` schema. Deterministic Python services then validate graph integrity, flag unsafe behavior, and execute simulations. This separation keeps runtime behavior testable and prevents model output from directly causing external side effects.

## Features

- Natural-language to typed workflow JSON
- Wati-style nodes: message, question, condition, API call, team assignment, wait, and end
- Deterministic graph and business-rule validation
- Plain-English flow explanation
- Interactive mock conversation with execution trace
- Mocked API calls, waits, and assignments
- SSRF-style dynamic API target detection
- DeepSeek model support with a limited, explicit no-key rule generator
- Responsive single-page UI served by FastAPI

## Quick start

Requires Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

The app works without an API key for a small set of English requirements. Offline rules recognize buyer/seller routing, pricing qualification using **more than N employees** with an optional **wait N minutes**, keyword-based team assignment with an optional wait, and an intentionally unsafe customer-supplied API URL example for validation. The rules copy the threshold, wait duration, trigger keyword, and team name into the flow. Unrecognized or incomplete requests return HTTP 422 with guidance; no unrelated default flow is generated. Example inputs are available as buttons in the UI.

For other requirements, put your DeepSeek API key in `.env` (loaded automatically on local startup), or set it in your shell:

```env
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

The default endpoint uses DeepSeek's `/chat/completions` API. Keep `.env` private; it is excluded by `.gitignore`. Restart the server after changing `.env`.

If DeepSeek is unavailable, a request covered by the offline rules can still run, with a visible notice. Other requests return an error rather than an invented flow. Help article and pricing URLs remain unresolved placeholders until real links are supplied; validation warns about them.

## Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/flows/generate` | Generate, explain, and validate a flow |
| `GET` | `/api/flows/{id}` | Retrieve a flow |
| `POST` | `/api/flows/{id}/validate` | Re-run deterministic validation |
| `POST` | `/api/flows/{id}/simulations` | Start a mock execution |
| `POST` | `/api/simulations/{id}/reply` | Submit an answer to the current question |

Replies include `{ "value": "Buyer", "expected_version": 0 }`, using the `version` returned when the simulation starts or last advances. A stale or duplicate reply returns `409`; only the first reply changes the trace. Restarting the server clears sessions.

Interactive OpenAPI documentation is available at <http://127.0.0.1:8000/docs>.

## Validation rules

The validator checks, among other things:

- missing start/end nodes and broken references
- unreachable nodes and graph cycles
- conditions that reference variables not collected on every incoming path
- reachable cycles that could prevent a branch from finishing
- conditions without fallback paths
- unresolved Wati team IDs
- API calls without failure paths
- dynamic or insecure API destinations
- overly long waits and unknown message variables

Flows with blocking errors cannot be simulated. Warnings remain visible but do not block testing.

## Tests

```powershell
pytest -q
```

The tests cover graph validation, unsafe API detection, both Buyer/Seller branches, rule parameter extraction, unsupported requests, provider failure, invalid input, and duplicate simulation replies.

## Project structure

```text
app/
?????? domain/          # Typed nodes, validation, and deterministic simulator
?????? services/        # LLM/demo generator and plain-English explanation
?????? static/          # Interactive single-page UI
?????? main.py          # FastAPI routes
?????? repositories.py  # Thread-safe in-memory storage
tests/               # Unit tests for core behavior
docs/                # Take-home write-up and demo script
```

## Current trade-offs

- Storage is deliberately in memory; restarting the process clears flows and simulations.
- The visual view is a lightweight responsive flow representation, not a drag-and-drop editor.
- External actions are always mocked. There is no publish-to-Wati operation.
- The offline rule generator recognizes a limited English grammar; arbitrary intent requires a configured model. Unsupported inputs fail explicitly.
- The first version uses binary conditions to keep the execution engine small and auditable.

## V2

- Wati team/template catalog integration and channel compatibility checks
- human approval and publish workflow
- versioning, flow diffs, and generated regression tests
- allow-listed API connector configuration and secret vault
- persistent execution/audit records and OpenTelemetry traces
- multi-turn clarification when the user intent is ambiguous

