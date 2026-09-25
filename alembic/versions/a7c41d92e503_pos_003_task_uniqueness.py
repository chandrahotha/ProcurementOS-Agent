"""pos_003: task uniqueness per (mission, plan_version, key)

Revision ID: a7c41d92e503
Revises: fe916f84b2d4
Create Date: 2026-09-25

Dedupes existing task rows (keeping the newest plan version per key), then
adds the unique index that backstops the plan_version-pinned task select
(bugs/01-backend.md B2).
"""

from alembic import op

revision = "a7c41d92e503"
down_revision = "fe916f84b2d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM pos_mission_task a
        USING pos_mission_task b
        WHERE a.mission_id = b.mission_id
          AND a.key = b.key
          AND (a.plan_version < b.plan_version
               OR (a.plan_version = b.plan_version AND a.created_at < b.created_at))
        """
    )
    op.create_index(
        "ix_pos_task_mission_version_key",
        "pos_mission_task",
        ["mission_id", "plan_version", "key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_pos_task_mission_version_key", table_name="pos_mission_task")
