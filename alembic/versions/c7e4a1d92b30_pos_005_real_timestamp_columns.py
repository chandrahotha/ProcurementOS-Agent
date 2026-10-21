"""pos_005: real timestamp columns (B44)

Revision ID: c7e4a1d92b30
Revises: b8d52e03f614
Create Date: 2026-10-20

Three columns held an ISO-8601 timestamp inside a VARCHAR(64):

    pos_mission.deadline
    pos_approval.expires_at
    pos_transaction.ordered_at

String comparison of timestamps is lexicographic, so "2026-1-2" sorted after
"2026-10-1", and an unparseable value had to be *guessed* at read time —
`app/approvals/service.py::_expired` had to treat a value it could not parse
as expired, because a VARCHAR cannot refuse to hold a non-timestamp.

This migration converts them to `TIMESTAMP WITH TIME ZONE`, which fixes both
problems at the storage layer: the comparison is a real timestamp comparison
and the database refuses a value that is not a timestamp.

The conversion is done in Python rather than with `ALTER COLUMN ... TYPE ...
USING` because SQLite (the dev/test engine) has no such clause and the two
engines disagree about how to cast an ISO string to a timestamp. The row
counts involved are small, and a portable loop is worth more here than a
faster engine-specific one.

Conversion policy per column (deliberate, not incidental):

* `pos_mission.deadline`      — unparseable -> NULL ("no deadline"), so the
  intake checklist gate fails closed instead of passing on garbage.
* `pos_approval.expires_at`   — unparseable -> epoch, i.e. already expired.
  NULL here means "no expiry" and a broken expiry must not become
  "never expires".
* `pos_transaction.ordered_at` — unparseable -> NULL (an order date is
  descriptive; a wrong one is worse than a missing one).
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "c7e4a1d92b30"
down_revision = "b8d52e03f614"
branch_labels = None
depends_on = None

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _parse(raw: object) -> datetime | None:
    """Parse an ISO-8601 string (or datetime) into an aware datetime."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _convert(
    table: str,
    column: str,
    *,
    on_unparseable: datetime | None,
) -> None:
    """Rewrite a VARCHAR column of ISO timestamps as real timestamps.

    Reads the column, parses it in Python, and writes the parsed value back
    through the connection so the value lands in the column with the type the
    database now enforces.
    """
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(f'SELECT id, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL')  # noqa: S608
    ).fetchall()
    for row_id, raw in rows:
        parsed = _parse(raw)
        value = on_unparseable if parsed is None else parsed
        bind.execute(
            sa.text(f'UPDATE "{table}" SET "{column}" = :value WHERE id = :id'),  # noqa: S608
            {"value": value, "id": row_id},
        )


def upgrade() -> None:
    # --- expand: the data is converted while the columns are still VARCHAR ---
    _convert("pos_mission", "deadline", on_unparseable=None)
    _convert("pos_approval", "expires_at", on_unparseable=EPOCH)
    _convert("pos_transaction", "ordered_at", on_unparseable=None)

    # --- contract: the columns become real timestamps ---
    for table, column in (
        ("pos_mission", "deadline"),
        ("pos_approval", "expires_at"),
        ("pos_transaction", "ordered_at"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                column,
                type_=sa.DateTime(timezone=True),
                existing_type=sa.String(length=64),
                existing_nullable=True,
                # Postgres will not cast VARCHAR to TIMESTAMPTZ on its own
                # ("cannot be cast automatically to type timestamp with
                # time zone"), and the values are now ISO-8601 strings, so
                # the cast is stated rather than assumed. SQLite has no
                # USING clause and ignores this: its batch mode recreates
                # the table and coerces the values in Python, which is why
                # the local chain passed while the Postgres one did not.
                postgresql_using=f'"{column}"::timestamptz',
            )


def downgrade() -> None:
    for table, column in (
        ("pos_mission", "deadline"),
        ("pos_approval", "expires_at"),
        ("pos_transaction", "ordered_at"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                column,
                type_=sa.String(length=64),
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=True,
                # The mirror of the upgrade: Postgres will not cast
                # TIMESTAMPTZ back to VARCHAR implicitly either.
                postgresql_using=f'"{column}"::text',
            )
    # The values are already strings in the app's ISO format once the
    # timestamp is rendered back out; re-writing them keeps the downgrade
    # lossless for the columns that carried a value.
    bind = op.get_bind()
    for table, column in (
        ("pos_mission", "deadline"),
        ("pos_approval", "expires_at"),
        ("pos_transaction", "ordered_at"),
    ):
        rows = bind.execute(
            sa.text(f'SELECT id, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL')  # noqa: S608
        ).fetchall()
        for row_id, raw in rows:
            # On SQLite the column is still a datetime here; on Postgres the
            # cast above has already turned it into text. Both are put back
            # into the ISO form the application reads.
            if isinstance(raw, datetime):
                text = raw.isoformat()
            else:
                parsed = _parse(raw)
                if parsed is None:
                    continue
                text = parsed.isoformat()
            bind.execute(
                sa.text(f'UPDATE "{table}" SET "{column}" = :value WHERE id = :id'),  # noqa: S608
                {"value": text, "id": row_id},
            )
