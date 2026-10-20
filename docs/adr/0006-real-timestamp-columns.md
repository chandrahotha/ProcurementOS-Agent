# ADR 0006 — Real timestamp columns instead of ISO strings in VARCHAR

- **Status:** accepted
- **Date:** 2026-10-20
- **Supersedes:** nothing
- **Related:** findings B44 (`bugs/01-backend.md`)

## Context

Three columns held an ISO-8601 timestamp inside a `VARCHAR(64)`:

- `pos_mission.deadline`
- `pos_approval.expires_at`
- `pos_transaction.ordered_at`

A timestamp stored as text is compared as text, so "2026-1-2" sorts after
"2026-10-1". Worse, a `VARCHAR` cannot refuse to hold a value that is not
a timestamp, so every read had to guess what an unparseable value meant.
`app/approvals/service.py::_expired` had to treat a value it could not
parse as *expired*, because the alternative — treating it as live — would
have let an approval execute forever. That was a policy decision hidden
inside a type mismatch.

The audit deferred this item (B44) as a "full DateTime-column migration",
which is a bigger piece of work than it needs to be: the three columns are
narrow, the conversion is mechanical, and the safety argument is
straightforward.

## Decision

Convert the three columns to `TIMESTAMP WITH TIME ZONE` and let the
database refuse a value that is not a timestamp.

- `pos_mission.deadline` — an unparseable value becomes NULL ("no
  deadline"), so the intake checklist gate fails closed rather than
  passing on garbage.
- `pos_approval.expires_at` — an unparseable value becomes the epoch,
  i.e. already expired. NULL here means "no expiry"; a broken expiry must
  not become "never expires".
- `pos_transaction.ordered_at` — an unparseable value becomes NULL. An
  order date is descriptive; a wrong one is worse than a missing one.

The conversion runs in Python inside migration `pos_005`, not as
`ALTER COLUMN ... TYPE ... USING`, because SQLite has no such clause and
the two engines disagree about how to cast an ISO string to a timestamp.
A portable loop over a few thousand rows is worth more here than a faster
engine-specific one.

The API keeps its ISO-8601 wire format. The browser and the API agree on
one representation, and the wire format is not where the type safety
belongs.

## Consequences

- `app/approvals/service.py::_expired` no longer has a "could not parse"
  branch, because the database cannot store a value it cannot parse.
- `_parse_deadline` in `app/api/missions.py` rejects a malformed deadline
  with a 422 before it reaches the database, and reads a naive datetime
  as UTC rather than as the server's local time.
- The wire format is unchanged: `deadline` and `expires_at` are still
  ISO-8601 strings in JSON.
- `pos_005` is reversible. The downgrade writes the values back out as
  ISO strings, so the round-trip is lossless.

## Brain refs

`prerequisite-docs/03_DOMAIN_MODEL.md` (typed timestamps), brain 04 §1
(the state machine reads `deadline`), brain 08 (expiry is a control, and
a control that can hold garbage is not a control).

## Rollback

`alembic downgrade -1` returns the columns to `VARCHAR(64)`. The
rehearsal in `scripts/rollback.py` exercises exactly that path against a
scratch database.
