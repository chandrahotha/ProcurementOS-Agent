"""Foundation entities (owned natively). Table prefix pos_ (brain 03 §1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScoped

PREFIX = "pos_"


class Tenant(TenantScoped):
    __tablename__ = f"{PREFIX}tenant"
    # Tenant rows carry their own id as tenant_id for uniformity.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    retention_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class User(TenantScoped):
    __tablename__ = f"{PREFIX}user"
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    # Real credential login (PBKDF2-SHA256, salted); sessions below.
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Dev/test only: bearer token handle. Prod uses OIDC subjects.
    api_token: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    # Prod OIDC subject (globally unique per issuer); null until linked.
    oidc_sub: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True)

    __table_args__ = (Index("ix_pos_user_tenant_email", "tenant_id", "email", unique=True),)


class UserSession(TenantScoped):
    """Real login sessions: bearer tokens hashed at rest with expiry (B-auth)."""

    __tablename__ = f"{PREFIX}session"
    user_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_ip: Mapped[str] = mapped_column(String(64), default="")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Role(TenantScoped):
    __tablename__ = f"{PREFIX}role"
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    permissions: Mapped[list[Any]] = mapped_column(JSON, default=list)


class Workspace(TenantScoped):
    __tablename__ = f"{PREFIX}workspace"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    budget_currency: Mapped[str] = mapped_column(String(3), default="EUR")
    members: Mapped[list[Any]] = mapped_column(JSON, default=list)  # [{user_id, roles[]}]


class Supplier(TenantScoped):
    __tablename__ = f"{PREFIX}supplier"
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="DE")
    contacts: Mapped[list[Any]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="active")
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class SupplierSite(TenantScoped):
    __tablename__ = f"{PREFIX}supplier_site"
    supplier_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="de-DE")
    incoterm_default: Mapped[str] = mapped_column(String(16), default="DAP")
    lead_time_days: Mapped[int] = mapped_column(Integer, default=14)


class Item(TenantScoped):
    __tablename__ = f"{PREFIX}item"
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general")
    base_uom: Mapped[str] = mapped_column(String(16), default="pcs")
    spec: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Document(TenantScoped):
    __tablename__ = f"{PREFIX}document"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="quote")
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime: Mapped[str] = mapped_column(String(128), default="application/pdf")
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="quarantined")
    source: Mapped[str] = mapped_column(String(64), default="upload")
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class DocumentVersion(TenantScoped):
    __tablename__ = f"{PREFIX}document_version"
    document_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    s3_key: Mapped[str] = mapped_column(String(1024), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    scan_verdict: Mapped[str] = mapped_column(String(32), default="pending")


class EvidenceSpan(TenantScoped):
    __tablename__ = f"{PREFIX}evidence_span"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    document_version: Mapped[int] = mapped_column(Integer, default=1)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_start: Mapped[int] = mapped_column(Integer, default=0)
    text_end: Mapped[int] = mapped_column(Integer, default=0)
    quoted_text: Mapped[str] = mapped_column(Text, default="")
    field_name: Mapped[str] = mapped_column(String(128), default="")
    field_value: Mapped[str] = mapped_column(Text, default="")
    extractor: Mapped[str] = mapped_column(String(64), default="heuristic-v1")
    extractor_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    instruction_flag: Mapped[bool] = mapped_column(Boolean, default=False)


class Transaction(TenantScoped):
    """Own purchase ledger feeding supplier_intel KPIs (OTD/acceptance/PPM)."""

    __tablename__ = f"{PREFIX}transaction"
    supplier_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    item_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, default=0)
    on_time: Mapped[bool] = mapped_column(Boolean, default=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=True)
    defects: Mapped[int] = mapped_column(Integer, default=0)
    price_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    ordered_at: Mapped[str] = mapped_column(String(64), default="")
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class AIJob(TenantScoped):
    __tablename__ = f"{PREFIX}ai_job"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="primary")
    model_version: Mapped[str] = mapped_column(String(64), default="mock-1")
    prompt_version: Mapped[str] = mapped_column(String(64), default="p1")
    tool_version: Mapped[str] = mapped_column(String(64), default="t1")
    input_hash: Mapped[str] = mapped_column(String(64), default="")
    output_hash: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class AIResult(TenantScoped):
    __tablename__ = f"{PREFIX}ai_result"
    job_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    schema_name: Mapped[str] = mapped_column(String(64), default="")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSON, default=list)
    label: Mapped[str] = mapped_column(String(64), default="AI draft")


class Approval(TenantScoped):
    __tablename__ = f"{PREFIX}approval"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    action_class: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), default="")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    lane: Mapped[str] = mapped_column(String(32), default="managerial")
    requested_by: Mapped[str] = mapped_column(String(32), default="")
    approvers_required: Mapped[int] = mapped_column(Integer, default=1)
    decisions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    expires_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AuditEvent(TenantScoped):
    __tablename__ = f"{PREFIX}audit_event"
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mission_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), default="")
    object_type: Mapped[str] = mapped_column(String(64), default="")
    object_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    before_hash: Mapped[str] = mapped_column(String(64), default="")
    after_hash: Mapped[str] = mapped_column(String(64), default="")
    prev_hash: Mapped[str] = mapped_column(String(64), default="GENESIS")
    event_hash: Mapped[str] = mapped_column(String(64), default="")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="api")
