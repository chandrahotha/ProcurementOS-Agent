"""Roles, lanes, permissions. Deny-by-default RBAC (brain 08 §2)."""

from __future__ import annotations

BUYER = "Buyer"
MANAGER = "ProcurementManager"
FINANCE = "FinanceReviewer"
COMPLIANCE = "ComplianceReviewer"
ADMIN = "Admin"

ALL_ROLES = [BUYER, MANAGER, FINANCE, COMPLIANCE, ADMIN]

# action -> roles allowed to REQUEST (decide is lane-checked separately)
REQUEST_ROLES: dict[str, list[str]] = {
    "mission.create": [BUYER, MANAGER, ADMIN],
    "mission.edit": [BUYER, MANAGER, ADMIN],
    "plan.generate": [BUYER, MANAGER, ADMIN],
    "plan.acknowledge": [MANAGER],
    "task.retry": [BUYER, MANAGER, ADMIN],
    "task.review": [BUYER, MANAGER, ADMIN],
    "evidence.correct": [BUYER, MANAGER, ADMIN],
    "analyze.run": [BUYER, MANAGER, ADMIN],
    "scenario.create": [BUYER, MANAGER, ADMIN],
    "scenario.optimize": [MANAGER],
    "draft.create": [BUYER, MANAGER, ADMIN],
    "approval.request": [BUYER, MANAGER, ADMIN],
    "action.dryrun": [BUYER, MANAGER, ADMIN],
    "action.execute": [BUYER, MANAGER, ADMIN],
    "export.request": [BUYER, MANAGER, ADMIN],
    "run.replay": [MANAGER],
}

# approval lane -> roles allowed to DECIDE in that lane
LANE_ROLES: dict[str, list[str]] = {
    "finance": [FINANCE, MANAGER],
    "compliance": [COMPLIANCE, MANAGER],
    "managerial": [MANAGER],
}

# Admin is config-only: cannot approve own missions (enforced in approvals service).
