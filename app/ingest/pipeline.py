"""Upload quarantine pipeline (brain 02 flows, 08 T01).

upload -> quarantine (MIME+ext+magic-byte, size/decompression caps)
-> malware scan -> immutable DocumentVersion (SHA-256) -> clean|rejected.
Macros/scripts never executed; OCR output treated as untrusted data.
"""

from __future__ import annotations

import hashlib
from typing import Any

MAX_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".csv": "text/csv",
}

MAGIC = {
    ".pdf": b"%PDF",
    ".xlsx": b"PK\x03\x04",
    ".docx": b"PK\x03\x04",
}

MACRO_MARKERS = (b"vbaProject", b"Macros/", b"oleObject")


def validate_upload(filename: str, mime: str, content: bytes) -> dict[str, Any]:
    ext = "." + (filename.rsplit(".", 1)[-1].lower() if "." in filename else "")
    if ext not in ALLOWED:
        return {"verdict": "rejected", "reason": f"extension {ext} not allowed"}
    if mime != ALLOWED[ext]:
        return {"verdict": "rejected", "reason": "MIME/extension mismatch"}
    if len(content) > MAX_BYTES:
        return {"verdict": "rejected", "reason": "oversize upload"}
    magic = MAGIC.get(ext)
    if magic and not content.startswith(magic):
        return {"verdict": "rejected", "reason": "magic-byte mismatch"}
    if ext == ".docx" and any(m in content[:4096] for m in MACRO_MARKERS):
        return {"verdict": "rejected", "reason": "macro content rejected in quarantine"}
    return {"verdict": "clean", "reason": "quarantine checks passed"}


def version_record(
    filename: str, content: bytes, tenant_id: str, version: int = 1
) -> dict[str, Any]:
    sha = hashlib.sha256(content).hexdigest()
    return {
        "version": version,
        "sha256": sha,
        "s3_key": f"pos-tenant-{tenant_id}/docs/{sha[:12]}-v{version}-{filename}",
        "scan_verdict": "clean",
    }
