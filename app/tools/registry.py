"""Closed tool registry (brain 04 §3). THE ONLY action surface.

14 tools, versioned, permission-mapped, idempotency-keyed (writes), audit-wrapped.
AI and workers dispatch ONLY through registry.dispatch. No shell/SQL/HTTP generics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.money import FxRate


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

    On the payload hash: the registry checks that a material tool was
    *authorised* (an approval id is present), not that the payload still
    matches the approved one. The payload-hash match is enforced one layer
    up, in `app.approvals.service.quorum_met`, which selects the approval
    row by `Approval.payload_hash == payload_hash(payload)` — an approved
    payload that was edited after approval matches no row and quorum fails.
    `app.actions.service.execute` calls quorum_met *before* it dispatches, so
    a material tool is never reached with an unmatched payload.
    """
    tool = ALLOWLIST.get(name)
    if tool is None:
        raise UnknownToolError(f"unknown tool {name!r}: rejected (closed registry)")
    if tool.name in MATERIAL_TOOLS and not approval_id:
        raise ToolDeniedError(f"{name} requires quorum approval")
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
    # Extract-only / gate surfaces (extract_candidates proposes, material tools
    # execute via actions/service, log_timeline persists): passthrough by design.
    return {"echo": args}


def _fx_of(raw: Any) -> FxRate | None:
    from decimal import Decimal

    from engine.money import FxRate

    if not isinstance(raw, dict):
        return None
    rate = raw.get("rate")
    try:
        rate_d = Decimal(str(rate)) if rate is not None else None
    except Exception:
        rate_d = None
    if rate_d is None:
        return None
    return FxRate(
        pair=str(raw.get("pair", "")),
        rate=rate_d,
        source=str(raw.get("source", "")),
        quoted_at=str(raw.get("quoted_at", "")),
    )


def _normalize_quote_line(args: dict[str, Any]) -> dict[str, Any]:
    from dataclasses import asdict
    from decimal import Decimal

    from engine.sourcing_compare import QuoteLine, normalize_line

    ql = QuoteLine(
        line_id=str(args.get("line_id", "")),
        supplier_id=str(args.get("supplier_id", "")),
        qty=Decimal(str(args.get("qty", "0"))),
        uom=str(args.get("uom", "")),
        unit_price_minor=int(args.get("unit_price_minor", 0)),
        currency=str(args.get("currency", "")),
        tax_mode=str(args.get("tax_mode", "")),
        tax_rate=Decimal(str(args.get("tax_rate", "0"))),
        price_uom=str(args.get("price_uom", "") or ""),
    )
    return asdict(
        normalize_line(
            ql,
            str(args.get("base_uom", "pcs")),
            str(args.get("target_ccy", "INR")),
            _fx_of(args.get("fx")),
        )
    )


def _rank(args: dict[str, Any]) -> dict[str, Any]:
    from dataclasses import asdict

    from engine.sourcing_compare import NormalizedLine, rank_lines

    lines = [
        NormalizedLine(
            line_id=str(ln.get("line_id", "")),
            supplier_id=str(ln.get("supplier_id", "")),
            normalized_total_minor=int(ln.get("normalized_total_minor", 0)),
            compliant=bool(ln.get("compliant", True)),
        )
        for ln in args.get("lines", [])
    ]
    return {"lines": [asdict(n) for n in rank_lines(lines)]}


def _kpis(args: dict[str, Any]) -> dict[str, Any]:
    from engine.supplier_intel import compute_kpis

    return compute_kpis(list(args.get("transactions", [])))


def _draft_message(args: dict[str, Any]) -> dict[str, Any]:
    from app.negotiation.ladders import draft_within_ladder, ladder

    lad = ladder(
        int(args.get("candidate_cost_minor", 0)),
        int(args.get("batna_cost_minor", 0)),
    )
    return draft_within_ladder(int(args.get("draft_price_minor", 0)), lad)


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
    "normalize_quote_line": _normalize_quote_line,
    "compute_sourcing_rank": _rank,
    "compute_supplier_kpis": _kpis,
    "compute_tco": _tco,
    "score_risk": _risk,
    "optimize_scenario": _opt,
    "draft_message": _draft_message,
    "render_dry_run": _echo,
    "send_supplier_message": _echo,
    "issue_po_intent": _echo,
    "reserve_budget_intent": _echo,
    "export_report": _echo,
    "log_timeline": _echo,
}
