# ADR 0013 — The audit chain carries its own order

- **Status:** accepted
- **Date:** 2026-10-21
- **Related:** ADR 0006, ADR 0007; `bugs/01-backend.md` C20

## Context

The audit trail is a hash chain: every event carries the hash of the event
before it, so any alteration to a past event breaks every hash after it.
The chain is only as good as two things:

1. **It does not fork.** Two events must never claim the same predecessor.
2. **Its order is recoverable.** A reader has to be able to say which event
   came first, without trusting the clock.

Both were broken, and neither showed up in the local suite.

**The order.** The writer linked each event to the previous event's hash,
but the *verifier* re-derived the order from the rows with
`ORDER BY created_at, id`. `id` is `uuid4().hex` — random. So two events
that shared a `created_at` were walked in a random order, and the verifier
reported a chain that was intact as broken. This was the flake that made
`tests/test_api.py::test_full_mission_walk` fail intermittently, and it
would have blocked a mission from being reported as complete, on the
strength of a UUID's sort order.

**The fork.** The writer's head lookup is a read-modify-write: read the
head, link to it, insert. The in-process `asyncio.Lock` covered one
process, so on Postgres two concurrent requests could read the same head
and both link to it. The weekly Postgres leg had been failing for a month
for exactly this reason, and the failure had been read as "Postgres is
broken on this machine" rather than as a defect.

## Decision

**The chain carries its own order, and the verifier follows the links.**

- **The timestamps along a chain strictly increase.** The writer nudges
  `created_at` forward by a microsecond when the clock has not moved on
  since the previous event. The order is then recoverable from the rows,
  and it cannot tie — there is no tie-break to get wrong. The chain is the
  truth about order, not the clock; a nudge bounded by the previous event
  cannot run ahead of real time by more than the number of events that
  shared a microsecond.
- **The verifier walks the chain backwards from its head**, following
  `prev_hash`, instead of re-deriving the order from the rows. The head
  is the event no other event points at; the walk checks that each
  event's hash is the hash of its body chained to its predecessor, that
  the chain roots at `GENESIS`, that no event is missing, and that no
  event is unreachable (which is what a fork looks like from the head).
  A linked list is verified by following the links; the rows' physical
  order is not evidence of anything.
- **Concurrent appends are serialised by the database, not by the
  process.** On Postgres the writer takes a transaction-scoped advisory
  lock keyed on the tenant before the read-modify-write. The second
  appender blocks until the first commits, so it sees the first's event
  and links to it. The lock is released by the commit, so it cannot
  outlive the transaction or be stranded by a crash. SQLite needs no
  equivalent: it serialises writes itself, and the local engine is
  single-writer.

## Consequences

- **The order no longer depends on the clock agreeing with itself.** Two
  events in the same microsecond are still ordered, and the verification
  does not care what order the rows are read in.
- **The verification is stronger, not weaker.** Following the links
  detects everything the forward walk did — a tampered body, a removed
  event, a fork — and it detects a fork *as* a fork rather than as a
  break in the middle of the chain.
- **The writer serialises per tenant on Postgres.** Appends for one tenant
  are ordered by the database. Appends for different tenants are not
  serialised against each other, and never were.
- **A chain that is genuinely broken still reports `intact: false`** with
  the id of the offending event, so the release gate and the mission gate
  behave exactly as before for a real break.
- **`created_at` is now "when this event was appended, in chain order"**
  rather than "when the clock said". The difference is at most one
  microsecond per event that shared a microsecond with its predecessor.
