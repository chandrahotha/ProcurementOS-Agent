"""Report exports: tenant-scoped builders with evidence appendix (F16).

Formats PDF/XLSX/CSV. Server-side scope check: manifest lists ONLY in-scope
mission IDs. Export denied for out-of-scope/second-tenant smuggling (POS-EXP-01).
"""

from __future__ import annotations

import csv
import io
from typing import Any


class ExportDeniedError(Exception):
    pass


def assert_scope(
    tenant_id: str, mission_tenant: str, mission_ids: list[str], scope: list[str]
) -> None:
    if mission_tenant != tenant_id:
        raise ExportDeniedError("cross-tenant export denied")
    if any(m not in scope for m in mission_ids):
        raise ExportDeniedError("out-of-scope mission in export manifest")


def manifest(
    tenant_id: str, mission_ids: list[str], fmt: str, evidence_refs: list[str]
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "mission_ids": mission_ids,
        "format": fmt,
        "evidence_refs": evidence_refs,
        "watermark": f"tenant:{tenant_id}",
    }


def to_csv(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    if not rows:
        return b""
    w = csv.DictWriter(buf, fieldnames=sorted(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()
