#!/usr/bin/env python3
"""The SSRF / egress drill, against a live webhook host.

The release gate asks for "SSRF suite against live webhook hosts". This
runs the outbox delivery against a real HTTP server on localhost and
checks three things:

1. **Delivery works.** An approved supplier message is really posted to
   the webhook.
2. **The egress policy holds.** The same URL is refused when the host is
   not on the allowlist, and a non-http scheme is refused outright.
3. **A redirect is not followed.** The webhook answers 302 to a host that
   is not on the allowlist; the delivery must not follow it.

The server is started by the script, so the drill needs nothing but the
repository.

    python scripts/ssrf_drill.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RECEIVED: list[dict[str, Any]] = []


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"_raw": raw.decode("latin-1")}
        RECEIVED.append({"path": self.path, "payload": payload})
        if self.path == "/redirect":
            # Answer with a redirect to a host that is not on the
            # allowlist. The delivery must not follow it.
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Quiet."""


def _start_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--allowlist",
        default="127.0.0.1",
        help="the egress allowlist the drill configures (default: 127.0.0.1)",
    )
    args = ap.parse_args(argv)

    from app.core import egress

    server, base = _start_server()
    failures: list[str] = []
    try:
        # --- the policy -------------------------------------------------
        try:
            egress.check_url(f"{base}/webhook", allowlist=("127.0.0.1",))
        except egress.EgressDeniedError as exc:
            failures.append(f"the configured webhook was refused: {exc}")
        else:
            print(f"1) allowed destination accepted: {base}/webhook")

        try:
            egress.check_url("http://169.254.169.254/latest/meta-data/", allowlist=("127.0.0.1",))
        except egress.EgressDeniedError:
            print("2) a host outside the allowlist is refused")
        else:
            failures.append("a host outside the allowlist was NOT refused")

        for scheme in ("file:///etc/passwd", "gopher://x", "ftp://x"):
            try:
                egress.check_url(scheme, allowlist=())
            except egress.EgressDeniedError:
                print(f"3) scheme refused: {scheme}")
            else:
                failures.append(f"scheme was NOT refused: {scheme}")

        # --- the live delivery ------------------------------------------
        os.environ["OUTBOX_WEBHOOK_URL"] = f"{base}/webhook"
        os.environ["OUTBOX_WEBHOOK_ALLOWLIST"] = args.allowlist

        import asyncio

        from app.actions.service import _deliver
        from app.core.config import settings

        settings.outbox_webhook_url = f"{base}/webhook"

        class _Mo:
            recipient = "supplier@syn.example"
            subject = "Procurement update"
            body = "Synthetic drill body."
            mission_id = "m-drill"

        sent = asyncio.run(_deliver(_Mo()))
        if sent:
            print(f"4) delivery to the live webhook succeeded ({len(RECEIVED)} request(s))")
        else:
            failures.append("the live delivery did not succeed")
        if not RECEIVED:
            failures.append("the webhook received nothing")
        else:
            print(f"   webhook received: {json.dumps(RECEIVED[0]['payload'])[:120]}")

        # --- a redirect must not be followed -----------------------------
        before = len(RECEIVED)
        settings.outbox_webhook_url = f"{base}/redirect"
        asyncio.run(_deliver(_Mo()))
        after = len(RECEIVED)
        if after == before + 1:
            print("5) the redirect was received but NOT followed (one request only)")
        else:
            failures.append(f"the delivery followed the redirect ({after - before} extra requests)")

        # --- a disallowed host is not reached ----------------------------
        settings.outbox_webhook_url = "http://169.254.169.254/latest/meta-data/"
        sent = asyncio.run(_deliver(_Mo()))
        if not sent:
            print("6) a destination outside the allowlist was not delivered to")
        else:
            failures.append("a destination outside the allowlist WAS delivered to")
    finally:
        server.shutdown()
        server.server_close()

    if failures:
        print("\nDRILL FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("\nSSRF / egress drill passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
