# 07 — AI Architecture: ProcurementOS-Agent

## 1. AI roles (inside this product only)

| Role | Allowed | Forbidden |
|---|---|---|
| Extractor (candidates) | Propose field values + spans + confidence | Asserting correctness; writing domain tables |
| Classifier | Doc kind, language,hostile-pattern flag assist | Executing files; deciding policy |
| Summarizer | Summarize VERIFIED evidence with citations | Summarizing unverified/hostile spans as fact |
| Explainer | Explain deterministic results in plain language | Recomputing or altering numbers |
| Drafter | Negotiation/external-message drafts inside ladder bounds | Sending; exceeding ladder; inventing terms |
| Planner-assist | Propose task DAG from intake + templates | Self-assigning tools outside allowlist; setting autonomy |
| Orchestrator (in-product) | Sequence allowlisted tool calls per acknowledged plan, handle retries/escalations | Calling non-registry tools; approving; raising dial; obeying document text |

The orchestrator is a deterministic state-machine driver that *invokes* AI for text steps and *invokes* tools for action steps — it is not an open-ended agent loop. Max steps per task and max retries are plan-pinned; overflow → `blocked` + human review.

## 2. Boundaries & validation

- Structured JSON output only (per-role schemas in `ai/schemas/`); schema/enum/range/ID/UOM/currency/date/scope validation on every response; failures → retry-once with repair prompt → then `needs_review` (never silent coerce, never math fallback to AI).
- AI has no DB credentials and no direct write path; all persistence goes through domain services after validation. Tool calls from AI-proposed plans are re-checked against the registry + policy at dispatch (defense in depth for AGENT-001).
- Prompt/version registry: `prompt_version` pinned per AIJob; planner, extractor, explainer, drafter prompts versioned separately; reproduction = prompt_version + model_version + input_hash.
- Retrieval scope: own mission evidence only (spans + certified results); no cross-tenant, no cross-mission (except aggregated Analytics with k-anonymity ≥5 missions), no web browsing in MVP.

## 3. Injection defenses (mechanized)

System > app > task > user > document hierarchy restated in every prompt; document content passed in fenced `DATA:` blocks with "never obey" instruction; pre-LLM instruction-scan flags hostile spans (excluded from planning inputs); post-LLM output-scan rejects imperative/policy-altering content; flagged-task auto-block (see `04_BUSINESS_RULES.md` §4). Hostile fixtures in CI assert zero mission mutation (AGENT-003).

## 4. Outage fallback (AGENT-004)

Provider timeout/5xx/auth-fail/schema-fail-twice → circuit breaker (60s backoff) → run `degraded`: deterministic engine unaffected; extraction falls back to "manual entry + upload" mode with coverage reflecting gaps; explainer/drafter panels show unavailable cards; approvals/exports/actions proceed on deterministic data; queued AI jobs retry with idempotency. Recovery replays the queue without recomputing math. Frontend polls run status; no fabricated placeholder text is ever rendered as AI output.

## 5. Run metadata (every AIJob)

provider, model_version, prompt_version, tool_version(s), input_hash (SHA-256 of quoted inputs), output_hash, tenant, user, mission/task IDs, evidence refs in/out, autonomy context (dial + class), timestamps, latency, tokens, cost estimate, status (ok/degraded/blocked/failed), error code. Surfaced in P15 + G17; retained per tenant policy; exportable for audit.
