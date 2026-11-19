# 3–5 minute demo script

## 0:00–0:30 — Problem and architecture

“This demo converts natural-language automation intent into a typed Wati-style workflow. With DeepSeek configured, the model compiles intent; without a key, offline rules parse supported prompts. Validation and execution are deterministic Python services, so model output never directly causes an external action.”

## 0:30–1:40 — Buyer/seller routing

1. Select **Buyer / seller routing** and generate.
2. Show the Visual, JSON, and Explanation tabs.
3. Point out the unresolved team warning.
4. Start the simulation and choose Buyer.
5. Show the mocked Sales assignment and execution trace.
6. Restart and choose Seller to show the alternative branch.

## 1:40–2:40 — Lead qualification

1. Select **Lead qualification** and generate.
2. Explain the free-text input notice and Enterprise Sales team warning.
3. Start the test and enter `75`.
4. Show condition evaluation, fast-forwarded wait, team assignment, and trace.
5. Restart with `10` to show the self-service pricing path.

## 2:40–3:40 — Unsafe flow

1. Select **Risky API call** and generate.
2. Show the blocking dynamic URL/SSRF error and missing failure-path warning.
3. Point out that **Start test** is disabled.
4. Explain that API calls are mocked even for valid flows.

## 3:40–4:15 — Quality and trade-offs

Briefly show `pytest -q` and the FastAPI `/docs` page. Close with the deliberate exclusions: in-memory storage, no real Wati publishing, and lightweight visualization. Mention versioning, Wati catalog integration, connector allow-lists, and human approval as V2 work.

