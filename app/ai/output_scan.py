"""AI output scan: hallucination/refusal guard (POS-AI-HAL-01).

Every AI claim must carry evidence refs or be labeled analytical with zero
authority. Certified numbers are never altered by AI text.
"""

from __future__ import annotations

from typing import Any


def scan_output(payload: dict[str, Any]) -> dict[str, Any]:
    refs = payload.get("evidence_refs") or []
    label = str(payload.get("label", ""))
    text = str(payload.get("text", ""))
    if refs:
        return {"verdict": "accept", "reason": "evidence-linked"}
    if "analytical" in label.lower():
        return {"verdict": "accept-labeled", "reason": "labeled analytical, zero authority"}
    if not text.strip():
        return {"verdict": "reject", "reason": "empty output"}
    return {"verdict": "quarantine", "reason": "claim with no evidence refs"}
