"""pos_006: evidence conflict tracking (B45)

Revision ID: f1a9c47be205
Revises: c7e4a1d92b30
Create Date: 2026-10-20

The analysis gate refused to advance while `blocking_conflicts` was
non-zero, but the counter was hardcoded to 0 because corrections kept no
history: a second correction simply overwrote the first. The three-way diff
in `app/evidence/conflicts.py` was written for exactly this case and never
wired.

Two columns make the conflict real:

* `base_value`   — the value the span held before anybody corrected it. It
  is the "base" of the three-way diff.
* `conflict_state` — "" (no conflict), "conflict" (a correction disagreed
  with a pending one and was refused), "resolved".

Existing rows get an empty base (they have never been corrected through
this path) and no conflict, so the migration is additive and does not
change any gate's verdict for a mission that is already in flight.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f1a9c47be205"
down_revision = "c7e4a1d92b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pos_evidence_span",
        sa.Column("base_value", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "pos_evidence_span",
        sa.Column("conflict_state", sa.String(length=32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("pos_evidence_span", "conflict_state")
    op.drop_column("pos_evidence_span", "base_value")
