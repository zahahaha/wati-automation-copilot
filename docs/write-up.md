# Automation Builder Copilot — Take-home write-up

## Problem and MVP scope

Chatbot automation builders are powerful but require users to translate business intent into nodes, variables, branches, and failure paths. The MVP lets a user describe an automation in plain English, compiles the description into a typed Wati-style flow, explains and reviews it, and runs a safe mock conversation.

The MVP intentionally excludes authentication, persistent storage, a drag-and-drop editor, real Wati publishing, and real external actions. These exclusions keep the 4–8 hour exercise focused on backend correctness and the user-value loop.

## Architecture and key decisions

The system separates probabilistic interpretation from deterministic execution:

1. A generator turns intent into a Pydantic-backed `Flow` JSON artifact.
2. A deterministic validator checks references, reachability, termination, variables, fallback paths, and unsafe API configuration.
3. A deterministic state-machine simulator executes nodes until it needs user input or reaches an end state.
4. The UI renders the artifact, review issues, conversation, mocked actions, and trace.

The LLM is therefore a compiler, not the runtime. Model output cannot directly call APIs, assign teams, or publish a workflow. API calls, waits, and assignments are mocked during simulation, and a maximum step count prevents runaway loops.

## AI and agent usage

With an API key, DeepSeek converts natural-language requirements to the constrained schema; offline, a small rule parser extracts supported parameters and rejects unsupported intent. The deterministic reviewer checks either result. During development, an AI coding agent helped draft alternatives, create test scenarios, and review failure cases; I selected and checked the final domain model, execution semantics, validation thresholds, and security boundaries.

One review example: an AI-assisted repository review identified that separate locks around simulation reads and writes allowed two replies to read the same question. I checked the stored state and found that the simulator mutates its input in place, which could also change a stored session before save. I added a client-visible session version and made version check, state-copy, transition, and save one locked operation. A duplicate-reply regression test checks that the second request gets `409` and the trace advances once.

## Manual review

I manually reviewed node transitions, condition semantics (including 80 versus 81 for “more than 80”), simulation pause/resume behavior, unsafe URL handling, exception boundaries, and the three demonstration scenarios. I verified that invalid flows cannot enter simulation and that no simulator node performs an external side effect. Schema validity alone does not guarantee the requested routing: tests must separately assert Buyer → Sales and Seller → help article using execution traces.

## Trade-offs and V2

In-memory storage and a lightweight visual view reduce setup time. Offline rules cover a few English patterns and reject unsupported inputs; unresolved article and pricing links are surfaced as warnings. A production version would add persistent flows, Wati catalog integration, connector allow-lists, credentials, approval before publishing, observability, and generated regression suites. A clarification agent could ask follow-up questions for ambiguous intent.
