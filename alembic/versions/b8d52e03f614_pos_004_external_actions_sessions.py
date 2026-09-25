"""pos_004: real external actions + sessions

Revision ID: b8d52e03f614
Revises: a7c41d92e503
Create Date: 2026-09-25

Creates the external-action tables (purchase_order, budget_reservation,
message_outbox — the gated tools' real outputs) and pos_session (real
login sessions), plus pos_user.password_hash (PBKDF2 credential login).
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d52e03f614"
down_revision = "a7c41d92e503"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_user", sa.Column("password_hash", sa.String(length=256), nullable=True))
    op.create_table(
        "pos_session",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_ip", sa.String(length=64), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_pos_session_tenant_id", "pos_session", ["tenant_id"])
    op.create_index("ix_pos_session_user_id", "pos_session", ["user_id"])
    op.create_table(
        "pos_purchase_order",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mission_id", sa.String(length=32), nullable=False),
        sa.Column("supplier_id", sa.String(length=32), nullable=False),
        sa.Column("po_number", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("total_minor", sa.Integer(), nullable=True),
        sa.Column("lines", sa.JSON(), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("approval_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("po_number"),
    )
    op.create_index("ix_pos_po_tenant_id", "pos_purchase_order", ["tenant_id"])
    op.create_index("ix_pos_po_mission_id", "pos_purchase_order", ["mission_id"])
    op.create_index("ix_pos_po_supplier_id", "pos_purchase_order", ["supplier_id"])
    op.create_index(
        "ix_pos_po_mission_supplier", "pos_purchase_order", ["mission_id", "supplier_id"]
    )
    op.create_table(
        "pos_budget_reservation",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), nullable=False),
        sa.Column("mission_id", sa.String(length=32), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("approval_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_budget_reservation_tenant_id", "pos_budget_reservation", ["tenant_id"])
    op.create_index(
        "ix_pos_budget_reservation_workspace_id", "pos_budget_reservation", ["workspace_id"]
    )
    op.create_index(
        "ix_pos_budget_reservation_mission_id", "pos_budget_reservation", ["mission_id"]
    )
    op.create_table(
        "pos_message_outbox",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mission_id", sa.String(length=32), nullable=False),
        sa.Column("supplier_id", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=True),
        sa.Column("recipient", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.String(length=300), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("approval_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_message_outbox_tenant_id", "pos_message_outbox", ["tenant_id"])
    op.create_index("ix_pos_message_outbox_mission_id", "pos_message_outbox", ["mission_id"])
    op.create_index("ix_pos_message_outbox_supplier_id", "pos_message_outbox", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_pos_message_outbox_supplier_id", table_name="pos_message_outbox")
    op.drop_index("ix_pos_message_outbox_mission_id", table_name="pos_message_outbox")
    op.drop_index("ix_pos_message_outbox_tenant_id", table_name="pos_message_outbox")
    op.drop_table("pos_message_outbox")
    op.drop_index("ix_pos_budget_reservation_mission_id", table_name="pos_budget_reservation")
    op.drop_index("ix_pos_budget_reservation_workspace_id", table_name="pos_budget_reservation")
    op.drop_index("ix_pos_budget_reservation_tenant_id", table_name="pos_budget_reservation")
    op.drop_table("pos_budget_reservation")
    op.drop_index("ix_pos_po_mission_supplier", table_name="pos_purchase_order")
    op.drop_index("ix_pos_po_supplier_id", table_name="pos_purchase_order")
    op.drop_index("ix_pos_po_mission_id", table_name="pos_purchase_order")
    op.drop_index("ix_pos_po_tenant_id", table_name="pos_purchase_order")
    op.drop_table("pos_purchase_order")
    op.drop_index("ix_pos_session_user_id", table_name="pos_session")
    op.drop_index("ix_pos_session_tenant_id", table_name="pos_session")
    op.drop_table("pos_session")
    op.drop_column("pos_user", "password_hash")
