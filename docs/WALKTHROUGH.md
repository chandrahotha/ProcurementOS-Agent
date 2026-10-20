# Walkthrough — eight minutes on the agent

A guided pass over the product, in the order the work actually happens.
Every figure below is in **INR minor units** (paise) unless it says
otherwise; 100 minor units = ₹1.

Start the stack:

```powershell
python scripts/demo.py
```

Then open http://localhost:3000 and sign in as
`daniel.manager@syn.example` with the password `syn-Demo-2026!`.

The manager persona is the one that can walk the whole mission: the plan
acknowledgement, the gate advances and the managerial approval all require
it. A buyer is refused at those steps, correctly.

---

## 1 · Mission Control (30 s)

`/agent` shows the portfolio: a KPI row (active, awaiting-my-approval,
below the coverage gate, median coverage), the mission table, and the
timeline preview on the right.

Three demo missions are already there, in three different states. Open
**CNC Bracket Q4 – 1000 pcs** — it is at the approval gate with a pending
approval. Open **M6 Fastener Sourcing** in a second tab: it is blocked in
intake by a quarantined document.

The coverage ring on each row is the *evidence coverage* — the share of
the eight required fields that a span backs. The gate needs 80%.

## 2 · The mission header (30 s)

The header carries the nine-state progress rail, the coverage ring, and
the autonomy dial. The rail is the mission's state machine:

```
intake → plan → evidence → analysis → scenarios → negotiation → approval → action → report
```

The current state pulses; completed states are ticked. The autonomy dial
is the *dial* from the product brain: `ASSISTED` requires a human
confirmation for every tool call, `SUPERVISED` runs the automatic tools
and gates the material ones, `GUARDED` tightens the tolerances. Raising
it needs a manager.

## 3 · Intake and the quarantine (60 s)

`/agent/{id}/intake` — the document queue with a quarantine verdict per
file. A clean verdict is `clean`; a hostile document is `quarantined`
with the reason.

The intake checklist is the first gate. It needs a document, a title, a
workspace, a currency, a deadline and an autonomy level. A waiver needs
Compliance sign-off, not a buyer's flag.

## 4 · The plan and the task board (90 s)

`/agent/{id}/plan` — the plan's ten tasks as a DAG: the tool each one
calls, its autonomy class, its estimate, and what it depends on. The
manager acknowledges it; a buyer is refused.

`/agent/{id}/tasks` — the board. Each task carries the *canonical call
shape* for its tool, so the plan states exactly what it will invoke. The
tasks run in dependency order. On a deployment with a broker they go onto
the queue; without one they run in the API process, and the acknowledge
response says which happened (`"execution": "queue"` or `"inline"`).

## 5 · Evidence and the conflict gate (60 s)

`/agent/{id}/evidence` — the provenance truth. Every span names its
document, the field, the value, the page and the extractor version, with
a confidence badge.

Correct a span inline. Correct it **twice with different values** and
the second correction is refused with `409 evidence_conflict`: the first
correction stands, the span is marked conflicted, and the *analysis* gate
refuses to open until a human settles it. Reverting to the original value
or repeating the current one settles it. The three-way rule — both sides
must differ from the base *and* from each other — is what makes this a
conflict and not a mere difference.

## 6 · Analysis: the certified numbers (90 s)

`/agent/{id}/suppliers` — run the analysis suite. The ranking is a
comparison of landed unit price across currencies: the imported quote
(USD 11.80 per piece) is converted at the quoted USD/INR rate, so 80
pieces land at **₹78,824**.

`/agent/{id}/cost` — the TCO build-up as a waterfall per supplier: price,
freight, insurance, tooling, tax, less discounts. The certified figure is
the engine's; the screen only shows it.

`/agent/{id}/risk` — the weighted composite as a heatmap, with the rule
version that produced it. A cell shows the dimension score the engine
certified, not a re-computation.

## 7 · Scenarios, negotiation, and the brief (90 s)

`/agent/{id}/scenarios` — a candidate scenario from the optimiser. The
allocation is the greedy, capacity-aware default; it is certified by
construction, so the result does not depend on whether a solver is
installed.

`/agent/{id}/negotiation` — the ladder drawn as a track: opening, target,
walk-away, and the BATNA. The walk-away is a hard wall — a draft above it
is refused by the API. The rungs land on the target without overshooting
it.

`/agent/{id}/decision` — the brief. The ranked winner with its certified
TCO, the cited evidence lines, and the AI note. **The AI note is
labelled.** If it carries no evidence reference it is shown as an
uncited draft with a warning, never as a certified fact.

## 8 · Approval, action and the record (90 s)

`/agent/{id}/approval` — the gate. The lanes are computed by the server
from the certified value and the tenant's rule version, never from the
payload. For an award above INR 5,00,000 the managerial lane alone is not
enough: the finance lane joins, and the manager cannot decide it. Reject
needs a reason, and it goes into the audit trail.

`/agent/{id}/actions` — the action centre. The payload is carried from
the approval row, because the action is refused unless the payload hashes
to the approved one. Dry-run first; Execute is enabled only on `ALLOW`;
the receipt is idempotent, so a replay returns the original receipt rather
than a second PO.

`/agent/{id}/report` — the export. CSV, XLSX and PDF, each with a
manifest naming the missions and the evidence appendix.

`/audit` — the trail. The whole walk is there, hash-chained;
`/api/v1/audit/verify` re-walks it and reports whether it is intact.

---

## What to notice

- **The numbers never come from the model.** Every certified figure is
  the engine's; the AI writes prose about it, and the prose is labelled.
- **Nothing material happens without a human.** The award, the purchase
  order, the budget reservation and the supplier message are all behind a
  quorum, and the payload is hash-locked to what was approved.
- **Exceptions are visible.** Thin data, stale rates, hostile documents
  and unresolved conflicts are rendered as exception content, never as a
  silent default.
- **The trail is reconstructible.** `GET /api/v1/audit/verify` re-walks
  the chain and says whether it is intact.

## Where the demo stops

The demo is a **mechanism** study on a synthetic corpus. It shows that the
decision is traceable, gated and reproducible; it does not show that the
ranking matches what a procurement professional would choose. The
evaluation design, the threats to validity and the capabilities that are
specified but not implemented are in
[`EVALUATION.md`](EVALUATION.md).
