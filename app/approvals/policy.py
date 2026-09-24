"""Autonomy classes + approval policy matrix (brain 04 §2). Pure logic."""

from __future__ import annotations

from typing import Any

AUTO = "AUTO"
APPROVAL_REQUIRED = "APPROVAL-REQUIRED"

DIALS = ["ASSISTED", "SUPERVISED", "GUARDED"]

MATERIAL_CLASSES = [
    "AWARD",
    "FINANCIAL_COMMIT",
    "CONTRACTUAL_COMMIT",
    "EXTERNAL_COMM",
    "POLICY_OVERRIDE",
]

# action class -> (lanes required, quorum rule description)
POLICY: dict[str, dict[str, Any]] = {
    "AWARD": {"lanes": ["managerial", "finance"], "rule": "Manager + Finance if value > threshold"},
    "FINANCIAL_COMMIT": {"lanes": ["finance", "managerial"], "rule": "Finance + Manager dual"},
    "CONTRACTUAL_COMMIT": {
        "lanes": ["compliance", "managerial"],
        "rule": "Compliance + Manager dual",
    },
    "EXTERNAL_COMM": {"lanes": ["managerial"], "rule": "Manager or Compliance single + hash match"},
    "POLICY_OVERRIDE": {
        "lanes": ["managerial"],
        "rule": "overridden domain lane + Manager, expiry",
    },
}


def required_lanes(action_class: str, value_minor: int, threshold_minor: int) -> list[str]:
    if action_class == "AWARD":
        if value_minor > threshold_minor:
            return ["managerial", "finance"]
        return ["managerial"]
    return list(POLICY.get(action_class, {}).get("lanes", []))


def dial_allows_autonomy(dial: str, autonomy_class: str) -> bool:
    if autonomy_class == APPROVAL_REQUIRED:
        return False
    if dial == "ASSISTED":
        return False  # every tool call needs human confirm
    return True  # SUPERVISED default + GUARDED within caps
