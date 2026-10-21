#!/usr/bin/env python3
"""Boot the whole product in one command, with a complete mission in it.

    python scripts/demo.py                 # boot, seed, build the demo, print
    python scripts/demo.py --seed-only     # just the database
    python scripts/demo.py --no-build      # skip the Next.js build
    python scripts/demo.py --stop          # stop a running demo

What it does:

1. seeds the synthetic tenant (users, workspace, rule version, suppliers,
   items, transactions, documents),
2. builds the three demo missions through the real HTTP endpoints, so every
   screen has real data,
3. builds the web app if it is not built,
4. starts the API and the web app,
5. waits for both to answer, and prints the credentials and the URLs.

The database is a local sqlite file, so the demo needs no services beyond
Python and Node. Redis is optional: without it the plan's tasks run in the
API process instead of on the queue, which the API reports in the
acknowledge response.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "pos_demo.db"
DB_URL = f"sqlite+aiosqlite:///{DB.as_posix()}"
API_PORT = 8000
WEB_PORT = 3000

PERSONAS: tuple[tuple[str, str, str], ...] = (
    ("amara.buyer1@syn.example", "Buyer", "creates missions, uploads, analyses"),
    (
        "daniel.manager@syn.example",
        "ProcurementManager",
        "acknowledges plans, advances gates, decides the managerial lane",
    ),
    ("fatima.finance@syn.example", "FinanceReviewer", "the finance approval lane"),
    ("chen.compliance@syn.example", "ComplianceReviewer", "the compliance lane and waivers"),
    ("admin.seed@syn.example", "Admin", "everything, plus /api/v1/ops/*"),
)
# The seeded demo credential. It is synthetic, it is published in the
# runbook, and it authenticates nothing outside the local demo database.
PASSWORD = "syn-Demo-2026!"  # noqa: S105 - synthetic demo credential


def _say(text: str) -> None:
    """Print and flush, so the parent's narration interleaves correctly with
    the subprocess output it is running."""
    print(text, flush=True)


def _run(cmd: list[str]) -> int:
    _say(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=ROOT, check=False)  # noqa: S603
    return proc.returncode


def _wait(url: str, seconds: int = 60) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:  # noqa: S310
                if r.status < 500:
                    return True
        except Exception:
            time.sleep(1)
    return False


def seed() -> int:
    if DB.exists():
        DB.unlink()
    print("\n== seeding the synthetic tenant ==")
    rc = _run([sys.executable, "seed/seed_pos.py", "--tenant", "SYN-TENANT-01", "--db-url", DB_URL])
    if rc != 0:
        return rc
    print("\n== building the demo missions ==")
    return _run([sys.executable, "seed/make_demo_mission.py", "--db-url", DB_URL])


def build_web() -> int:
    if not (ROOT / "web" / "node_modules").exists():
        print("\n== installing the web dependencies ==")
        if _run(["npm", "install", "--prefix", "web"]) != 0:
            return 1
    print("\n== building the web app ==")
    return _run(["npm", "run", "build", "--prefix", "web"])


def start() -> int:
    env = {
        **os.environ,
        "DATABASE_URL": DB_URL,
        "DATABASE_SYNC_URL": DB_URL,
        "WEB_ORIGIN": f"http://localhost:{WEB_PORT}",
    }
    _say("\n== starting the API ==")
    api_log = open(ROOT / "pos_demo_api.log", "w", encoding="utf-8")  # noqa: SIM115
    api = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(API_PORT)],
        cwd=ROOT,
        env=env,
        stdout=api_log,
        stderr=subprocess.STDOUT,
    )
    _say("== starting the web app ==")
    web_log = open(ROOT / "pos_demo_web.log", "w", encoding="utf-8")  # noqa: SIM115
    npm = shutil.which("npm") or "npm"
    web = subprocess.Popen(  # noqa: S603
        [npm, "run", "start", "--prefix", "web"],
        cwd=ROOT,
        stdout=web_log,
        stderr=subprocess.STDOUT,
    )

    if not _wait(f"http://localhost:{API_PORT}/healthz"):
        print("the API did not come up; see pos_demo_api.log", file=sys.stderr)
        api.terminate()
        web.terminate()
        return 1
    if not _wait(f"http://localhost:{WEB_PORT}/agent"):
        print("the web app did not come up; see pos_demo_web.log", file=sys.stderr)
        api.terminate()
        web.terminate()
        return 1

    try:
        with urllib.request.urlopen(f"http://localhost:{API_PORT}/healthz", timeout=10) as r:
            health = json.load(r)["data"]
    except Exception as exc:  # pragma: no cover
        health = {"error": str(exc)}

    _say("")
    _say("=" * 68)
    _say("  ProcurementOS-Agent — demo running")
    _say("=" * 68)
    _say(f"  Web app     http://localhost:{WEB_PORT}")
    _say(f"  API         http://localhost:{API_PORT}/api/v1   (docs: /docs)")
    _say(f"  Database    {DB.name}   db={health.get('db')}  redis={health.get('redis')}")
    _say("")
    _say("  Sign in at /login with an email and a password.")
    _say(f"  Password (all personas): {PASSWORD}")
    _say("")
    for email, role, can in PERSONAS:
        _say(f"    {email:32s} {role:20s} {can}")
    _say("")
    _say("  The three demo missions are on Mission Control:")
    _say("    one at the approval gate (a pending approval),")
    _say("    one at the analysis gate (certified results, no decision),")
    _say("    one blocked in intake by a quarantined document.")
    _say("")
    _say("  A guided walk is in docs/WALKTHROUGH.md")
    _say("=" * 68)

    def _shutdown(*_: object) -> None:
        api.terminate()
        web.terminate()

    signal.signal(signal.SIGINT, _shutdown)
    try:
        api.wait()
    except KeyboardInterrupt:
        _shutdown()
    return 0


def stop() -> int:
    """Stop whatever is listening on the demo ports."""
    netstat = shutil.which("netstat") or "netstat"
    taskkill = shutil.which("taskkill") or "taskkill"
    for port in (API_PORT, WEB_PORT):
        try:
            out = subprocess.run(  # noqa: S603
                [netstat, "-ano"], capture_output=True, text=True, check=False
            ).stdout
        except OSError as exc:  # pragma: no cover - platform dependent
            _say(f"could not list the listening ports: {exc}")
            continue
        for line in out.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                pid = int(line.split()[-1])
                subprocess.run(  # noqa: S603
                    [taskkill, "/PID", str(pid), "/F"], capture_output=True, check=False
                )
                _say(f"stopped the process on :{port}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed-only", action="store_true", help="seed the database and stop")
    ap.add_argument("--no-build", action="store_true", help="do not build the web app")
    ap.add_argument("--stop", action="store_true", help="stop a running demo")
    args = ap.parse_args(argv)

    if args.stop:
        return stop()
    if seed() != 0:
        return 1
    if args.seed_only:
        return 0
    if not args.no_build and build_web() != 0:
        return 1
    return start()


if __name__ == "__main__":
    raise SystemExit(main())
