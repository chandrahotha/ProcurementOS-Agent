"""pos_003: task uniqueness per (mission, plan_version, key)

Revision ID: a7c41d92e503
Revises: fe916f84b2d4
Create Date: 2026-09-25

Dedupes existing task rows (keeping the newest plan version per key), then
adds the unique index that backstops the plan_version-pinned task select
(bugs/01-backend.md B2).

The dedupe statement is written in portable SQL. It used to be
`DELETE FROM pos_mission_task a USING pos_mission_task b ...`, which is
Postgres-only: running the migration chain against sqlite — the engine the
dev and test stack uses — failed with "near \"a\": syntax error", so the
"round-trip verified on scratch sqlite" claim in docs/RELEASE_GATE.md was
never true. The portable form keeps the same ordering the application uses
when it picks the current plan version ((plan_version, created_at), with the
id as a final tie-break, so exactly one row survives each group).
"""

from alembic import op

revision = "a7c41d92e503"
down_revision = "fe916f84b2d4"
branch_labels = None
depends_on = None

_DEDUPE = """
DELETE FROM pos_mission_task
WHERE id IN (
    SELECT a.id
    FROM pos_mission_task a
    WHERE EXISTS (
        SELECT 1
        FROM pos_mission_task b
        WHERE b.mission_id = a.mission_id
          AND b.key = a.key
          AND (
                b.plan_version > a.plan_version
             OR (b.plan_version = a.plan_version AND b.created_at > a.created_at)
             OR (b.plan_version = a.plan_version AND b.created_at = a.created_at AND b.id > a.id)
          )
    )
)
"""


def upgrade() -> None:
    op.execute(_DEDUPE)
    op.create_index(
        "ix_pos_task_mission_version_key",
        "pos_mission_task",
        ["mission_id", "plan_version", "key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_pos_task_mission_version_key", table_name="pos_mission_task")
