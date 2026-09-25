"""External-action entities (brain 04 §1/§3): the 'action' claim becomes real.

These rows are created ONLY by the gated tools after quorum approval:
- PurchaseOrder: a real PO of record issued by `issue_po_intent`.
- BudgetReservation: a real budget hold by `reserve_budget_intent`.
- MessageOutbox: a transactional outbox row by `send_supplier_message`;
  delivery drains when a transport is configured, and a message NEVER
  sends without EXTERNAL_COMM approval.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScoped

PREFIX = "pos_"


class PurchaseOrder(TenantScoped):
    __tablename__ = f"{PREFIX}purchase_order"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    po_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), default="issued_intent")
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    total_minor: Mapped[int] = mapped_column(Integer, default=0)
    lines: Mapped[list[Any]] = mapped_column(JSON, default=list)
    payload_hash: Mapped[str] = mapped_column(String(64), default="")
    approval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (Index("ix_pos_po_mission_supplier", "mission_id", "supplier_id"),)


class BudgetReservation(TenantScoped):
    __tablename__ = f"{PREFIX}budget_reservation"
    workspace_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    status: Mapped[str] = mapped_column(String(32), default="reserved")
    payload_hash: Mapped[str] = mapped_column(String(64), default="")
    approval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class MessageOutbox(TenantScoped):
    __tablename__ = f"{PREFIX}message_outbox"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="email")
    recipient: Mapped[str] = mapped_column(String(320), default="")
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    # queued | sent | failed — delivery is transport-gated, approval-gated upstream
    status: Mapped[str] = mapped_column(String(32), default="queued")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), default="")
    approval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
