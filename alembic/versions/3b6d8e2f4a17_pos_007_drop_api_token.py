"""pos_007: drop the developer-token column

Revision ID: 3b6d8e2f4a17
Revises: f1a9c47be205
Create Date: 2026-10-21

The dev-token fallback is gone. A request is now authenticated either by
an OIDC bearer token or by a session token minted from an email and a
password at `POST /api/v1/auth/login`. There is no third way in.

`pos_user.api_token` held the SHA-256 digest of a `dev-<email>` string,
which anybody can compute from a seeded email address without touching
the database. It has no reader left, so it is dropped rather than left
behind as a column that looks like a credential store and is not one.

Dropped rather than blanked: SQLite's DROP COLUMN is only supported from
3.35, so this uses alembic's batch mode, which recreates the table.
Nothing references `pos_user` with a foreign key — the schema has no
foreign keys at all — so the recreate cannot orphan a row.

Reversible: downgrade re-adds the column, nullable and unique, exactly
as it was.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "3b6d8e2f4a17"
down_revision = "f1a9c47be205"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pos_user") as batch:
        batch.drop_column("api_token")


def downgrade() -> None:
    with op.batch_alter_table("pos_user") as batch:
        # The uniqueness is restored as a *named* constraint: SQLite's table
        # recreate refuses an unnamed one ("Constraint must have a name").
        batch.add_column(sa.Column("api_token", sa.String(length=128), nullable=True))
        batch.create_unique_constraint("uq_pos_user_api_token", ["api_token"])
