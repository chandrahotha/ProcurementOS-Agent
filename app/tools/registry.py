"""Closed tool registry (brain 04 §3). THE ONLY action surface.

14 tools, versioned, permission-mapped, idempotency-keyed (writes), audit-wrapped.
AI and workers dispatch ONLY through registry.dispatch. No shell/SQL/HTTP generics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class UnknownToolError(Exception):
    pass


class ToolDeniedError(Exception):
    pass


@dataclass(frozen=True)
class ToolDef:
    name: str
    version: str
    autonomy_class: str  # AUTO | APPROVAL-REQUIRED
    idempotent: bool = False
    description: str = ""


ALLOWLIST: dict[str, ToolDef] = {
    "extract_candidates": ToolDef(
        "extract_candidates", "1.0.0", "AUTO", False, "Propose fields + spans"
    ),
    "normalize_quote_line": ToolDef(
        "normalize_quote_line", "1.0.0", "AUTO", False, "Normalize line"
    ),
    "compute_sourcing_rank": ToolDef("compute_sourcing_rank", "1.0.0", "AUTO", False, "Rank lines"),
    "compute_supplier_kpis": ToolDef("compute_supplier_kpis", "1.0.0", "AUTO", False, "KPIs"),
    "compute_tco": ToolDef("compute_tco", "1.0.0", "AUTO", False, "TCO build-up"),
    "score_risk": ToolDef("score_risk", "1.0.0", "AUTO", False, "Risk bands"),
    "optimize_scenario": ToolDef(
        "optimize_scenario", "1.0.0", "AUTO", False, "Constrained allocation"
    ),
    "draft_message": ToolDef("draft_message", "1.0.0", "AUTO", False, "Draft inside ladder"),
    "render_dry_run": ToolDef("render_dry_run", "1.0.0", "AUTO", False, "Dry-run preview"),
    "send_supplier_message": ToolDef(
        "send_supplier_message", "1.0.0", "APPROVAL-REQUIRED", True, "Gated send"
    ),
    "issue_po_intent": ToolDef(
        "issue_po_intent", "1.0.0", "APPROVAL-REQUIRED", True, "Gated PO intent"
    ),
    "reserve_budget_intent": ToolDef(
        "reserve_budget_intent", "1.0.0", "APPROVAL-REQUIRED", True, "Gated budget"
    ),
    "export_report": ToolDef("export_report", "1.0.0", "AUTO", True, "Tenant-scoped export"),
    "log_timeline": ToolDef("log_timeline", "1.0.0", "AUTO", False, "Append timeline"),
}

MATERIAL_TOOLS = {"send_supplier_message", "issue_po_intent", "reserve_budget_intent"}

TOOL_VERSIONS = {name: d.version for name, d in ALLOWLIST.items()}


def dispatch(
    name: str,
    args: dict[str, Any],
    *,
    actor_id: str = "",
    approval_id: str | None = None,
    idempotency_key: str = "",
) -> dict[str, Any]:
    """Dispatch with closed-registry + material-approval enforcement.

    - Unknown name -> UnknownToolError (caller audits unknown_tool_blocked).
    - Material tool without approval_id -> ToolDeniedError.
    - Write tools without idempotency key -> ToolDeniedError.
    Pure/deterministic: returns a result envelope; persistence is the caller's job.
    """
    tool = ALLOWLIST.get(name)
    if tool is None:
        raise UnknownToolError(f"unknown tool {name!r}: rejected (closed registry)")
    if tool.name in MATERIAL_TOOLS and not approval_id:
        raise ToolDeniedError(f"{name} requires quorum approval (payload hash match)")
    if tool.idempotent and not idempotency_key:
        raise ToolDeniedError(f"{name} requires Idempotency-Key")
    handler = _HANDLERS.get(name, _echo)
    return {
        "tool": name,
        "tool_version": tool.version,
        "autonomy_class": tool.autonomy_class,
        "result": handler(args),
    }


def _echo(args: dict[str, Any]) -> dict[str, Any]:
    return {"echo": args}


def _tco(args: dict[str, Any]) -> dict[str, Any]:
    from engine.cost_intel import tco

    return tco(
        int(args.get("price_minor", 0)),
        int(args.get("freight_minor", 0)),
        int(args.get("insurance_minor", 0)),
        int(args.get("tooling_minor", 0)),
        int(args.get("tax_minor", 0)),
        int(args.get("discount_minor", 0)),
    )


def _risk(args: dict[str, Any]) -> dict[str, Any]:
    from engine.risk_intel import score

    return score(dict(args.get("dimensions", {})))


def _opt(args: dict[str, Any]) -> dict[str, Any]:
    from engine.scenario_opt import allocate

    return allocate(int(args.get("demand", 0)), list(args.get("offers", [])))


_HANDLERS = {
    "extract_candidates": _echo,
    "normalize_quote_line": _echo,
    "compute_sourcing_rank": _echo,
    "compute_supplier_kpis": _echo,
    "compute_tco": _tco,
    "score_risk": _risk,
    "optimize_scenario": _opt,
    "draft_message": _echo,
    "render_dry_run": _echo,
    "send_supplier_message": _echo,
    "issue_po_intent": _echo,
    "reserve_budget_intent": _echo,
    "export_report": _echo,
    "log_timeline": _echo,
}
