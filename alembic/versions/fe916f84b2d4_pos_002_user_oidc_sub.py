"""pos_002 user oidc_sub

Revision ID: fe916f84b2d4
Revises: 333a21eef97c
Create Date: 2026-09-24 16:22:33.441137
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "fe916f84b2d4"
down_revision: str | Sequence[str] | None = "333a21eef97c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Batch mode: SQLite needs copy-and-move for constraints; Postgres
    # runs the same block as plain ALTERs. Reviewed, non-destructive.
    with op.batch_alter_table("pos_user") as batch:
        batch.add_column(sa.Column("oidc_sub", sa.String(length=256), nullable=True))
        batch.create_unique_constraint("uq_pos_user_oidc_sub", ["oidc_sub"])


def downgrade() -> None:
    with op.batch_alter_table("pos_user") as batch:
        batch.drop_constraint("uq_pos_user_oidc_sub", type_="unique")
        batch.drop_column("oidc_sub")
