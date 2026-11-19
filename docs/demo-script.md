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

1. Edit the prompt live to: `When a new lead asks for pricing, collect their company size. If they have more than 80 employees, wait 7 minutes and assign them to Enterprise Sales. Otherwise, send the self-service pricing page.` Generate and show the **generation mode** badge (AI generated or Offline rules).
2. Show JSON `check_size.value = 80` and `wait_for_sales.duration_seconds = 420`; explain the free-text input and team warnings.
3. Start the test and enter `80`. Show the false branch and self-service pricing page.
4. Restart and enter `81`. Show the true branch, fast-forwarded seven-minute wait, Enterprise Sales assignment, and trace.

## 2:40–3:40 — Unsafe flow

1. Select **Risky API call** and generate.
2. Show the blocking dynamic URL/SSRF error and missing failure-path warning.
3. Point out that **Start test** is disabled.
4. If time allows, show the direct API call to start a blocked flow returns `422`. Explain that API calls are mocked even for valid flows.

## 3:40–4:15 — Quality and trade-offs

Briefly show `pytest -q` and the FastAPI `/docs` page. Close with the deliberate exclusions: in-memory storage, no real Wati publishing, and lightweight visualization. Mention versioning, Wati catalog integration, connector allow-lists, and human approval as V2 work.

