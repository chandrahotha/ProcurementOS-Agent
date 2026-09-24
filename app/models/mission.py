"""Mission entities (brain 03 §2). product_case = Mission."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScoped

PREFIX = "pos_"
STATES = [
    "intake",
    "plan",
    "evidence",
    "analysis",
    "scenarios",
    "negotiation",
    "approval",
    "action",
    "report",
]


class Mission(TenantScoped):
    __tablename__ = f"{PREFIX}mission"
    workspace_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general")
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    budget_cap_minor: Mapped[int] = mapped_column(Integer, default=0)
    deadline: Mapped[str | None] = mapped_column(String(64), nullable=True)
    autonomy_level: Mapped[str] = mapped_column(String(16), default="SUPERVISED")
    state: Mapped[str] = mapped_column(String(32), default="intake")
    coverage_pct: Mapped[int] = mapped_column(Integer, default=0)
    rule_version: Mapped[str] = mapped_column(String(32), default="rv-1")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    state_history: Mapped[list[Any]] = mapped_column(JSON, default=list)
    lines: Mapped[list[Any]] = mapped_column(JSON, default=list)  # mission lines for W1
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class MissionPlan(TenantScoped):
    __tablename__ = f"{PREFIX}mission_plan"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    taskspecs: Mapped[list[Any]] = mapped_column(JSON, default=list)
    dag_hash: Mapped[str] = mapped_column(String(64), default="")
    diff_from_prev: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    acknowledged_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")

    __table_args__ = (Index("ix_pos_plan_mission_version", "mission_id", "version", unique=True),)


class MissionTask(TenantScoped):
    __tablename__ = f"{PREFIX}mission_task"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    plan_version: Mapped[int] = mapped_column(Integer, default=1)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="")
    tool_name: Mapped[str] = mapped_column(String(64), default="")
    args_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    assigned_role: Mapped[str] = mapped_column(String(64), default="Buyer")
    result_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSON, default=list)
    activity_log: Mapped[list[Any]] = mapped_column(JSON, default=list)


class MissionRun(TenantScoped):
    __tablename__ = f"{PREFIX}mission_run"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    plan_version: Mapped[int] = mapped_column(Integer, default=1)
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    inputs_hash: Mapped[str] = mapped_column(String(64), default="")
    rule_version: Mapped[str] = mapped_column(String(32), default="rv-1")
    tool_versions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_snapshot_hash: Mapped[str] = mapped_column(String(64), default="")
    step_log: Mapped[list[Any]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    sandbox_diff: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SourcingResult(TenantScoped):
    __tablename__ = f"{PREFIX}sourcing_result"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), index=True, default="")
    line_id: Mapped[str] = mapped_column(String(64), default="")
    supplier_id: Mapped[str] = mapped_column(String(32), index=True, default="")
    normalized_total_minor: Mapped[int] = mapped_column(Integer, default=0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    compliant_bool: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSON, default=list)


class CostResult(TenantScoped):
    __tablename__ = f"{PREFIX}cost_result"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), index=True, default="")
    supplier_id: Mapped[str] = mapped_column(String(32), default="")
    scenario_id: Mapped[str] = mapped_column(String(64), default="")
    tco_minor: Mapped[int] = mapped_column(Integer, default=0)
    build_up: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fx_sources: Mapped[list[Any]] = mapped_column(JSON, default=list)
    stale_flag: Mapped[bool] = mapped_column(Boolean, default=False)


class RiskResult(TenantScoped):
    __tablename__ = f"{PREFIX}risk_result"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), index=True, default="")
    supplier_id: Mapped[str] = mapped_column(String(32), default="")
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    weights_version: Mapped[str] = mapped_column(String(32), default="rv-1")
    composite: Mapped[int] = mapped_column(Integer, default=0)
    band: Mapped[str] = mapped_column(String(16), default="LOW")
    evidence_refs: Mapped[list[Any]] = mapped_column(JSON, default=list)


class ScenarioResult(TenantScoped):
    __tablename__ = f"{PREFIX}scenario_result"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), index=True, default="")
    scenario_id: Mapped[str] = mapped_column(String(64), default="")
    allocations: Mapped[list[Any]] = mapped_column(JSON, default=list)
    objective_value: Mapped[int] = mapped_column(Integer, default=0)
    constraints_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    savings_vs_baseline: Mapped[int] = mapped_column(Integer, default=0)
    candidate: Mapped[bool] = mapped_column(Boolean, default=False)


class SourceLink(TenantScoped):
    __tablename__ = f"{PREFIX}source_link"
    result_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    evidence_span_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    role: Mapped[str] = mapped_column(String(32), default="supporting")


class RuleVersion(TenantScoped):
    __tablename__ = f"{PREFIX}rule_version"
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[str] = mapped_column(String(64), default="")
    weights: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tolerances: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fx_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    changelog: Mapped[str] = mapped_column(Text, default="")


class TimelineEvent(TenantScoped):
    """Read projection helper persisted for replay scrubber (P01/P15)."""

    __tablename__ = f"{PREFIX}timeline_event"
    mission_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
