"""Upload quarantine pipeline (brain 02 flows, 08 T01).

upload -> quarantine (MIME+ext+magic-byte, size cap) -> archive-content
macro scan -> immutable DocumentVersion (SHA-256) -> clean|rejected.
Macros/scripts never executed; OCR output treated as untrusted data.
The quarantine checks are MIME/extension/magic-byte/archive scans — not an
antivirus; that is the documented scope of "malware scan" here (B58).
Object bytes are stored in the configured S3-compatible bucket when
S3 upload succeeds (B50); the sha256/s3_key always describe the real bytes.
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
    if ext in (".docx", ".xlsx"):
        # Full-archive macro scan (B26): vbaProject.bin sits deep in the OOXML
        # zip (central directory at the end), so a first-4096-bytes grep is
        # trivially bypassed. Scan the whole content for both formats.
        if any(m in content for m in MACRO_MARKERS):
            return {"verdict": "rejected", "reason": "macro content rejected in quarantine"}
    return {"verdict": "clean", "reason": "quarantine checks passed"}


def version_record(
    filename: str, content: bytes, tenant_id: str, version: int = 1
) -> dict[str, Any]:
    sha = hashlib.sha256(content).hexdigest()
    # B28: the raw client filename never reaches the key — path separators
    # are neutralized so a traversal-style name cannot escape the prefix.
    safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1] or "upload.bin"
    key = f"pos-tenant-{tenant_id}/docs/{sha[:12]}-v{version}-{safe_name}"
    # B50: the bytes are stored in the configured S3-compatible bucket when
    # credentials exist; without credentials the key still describes the
    # intended location (local/dev keeps the record, upload is a no-op).
    stored = put_object(key, content)
    return {
        "version": version,
        "sha256": sha,
        "s3_key": key,
        "scan_verdict": "clean",
        "stored": stored,
    }


def put_object(key: str, content: bytes) -> bool:
    """Store bytes in the configured S3-compatible bucket (B50). Best-effort:
    returns False when credentials/bucket are unavailable (local dev)."""
    try:
        import boto3

        from app.core.config import settings

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
        client.put_object(Bucket=settings.s3_bucket, Key=key, Body=content)
        return True
    except Exception:
        return False
