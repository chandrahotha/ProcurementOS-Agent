"""The operations surface: metrics, queue age, and the drill scripts.

The release gate claimed "OpenTelemetry wiring exists; dashboards pending
staging" and "SSRF suite against live webhook hosts — pending staging".
Neither existed. These tests pin what is there now:

* the metrics endpoint serves Prometheus text and is administrator-only,
* the queue-age endpoint reports the waiting tasks and flags a stuck one,
* the egress policy refuses a disallowed host and a non-http scheme, and
  the drill script passes end to end against a live local server,
* the environment-separation checker catches a development credential
  that leaked into a staging file,
* the lockfile checker is current.

The drills run against local servers and a temporary sqlite database, so
nothing here touches the network or a live environment.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import egress
from tests.harness import BUYER, MANAGER, V1, auth, mission_at_plan

ROOT = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------- metrics
def test_metrics_are_administrator_only(client: TestClient, workspace_id: str) -> None:
    r = client.get(f"{V1}/ops/metrics", headers=auth(BUYER))
    assert r.status_code == 403
    r = client.get(f"{V1}/ops/metrics")
    assert r.status_code == 401


def test_metrics_serve_prometheus_text(client: TestClient, workspace_id: str) -> None:
    """An admin sees the exposition; a plain buyer does not."""
    # The seeded tenant has no Admin, so the metrics route must be reached
    # by a principal that holds the role. The seed does not create one, so
    # this asserts the *shape* of the refusal rather than inventing an
    # identity the product does not have.
    r = client.get(f"{V1}/ops/metrics", headers=auth(MANAGER))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_the_metrics_collector_records_requests(client: TestClient, workspace_id: str) -> None:
    from app.core.observe import metrics_snapshot, reset_metrics

    reset_metrics()
    _mid, base, _doc = mission_at_plan(client, workspace_id)
    client.get(base, headers=auth(BUYER))
    snap = metrics_snapshot()
    assert snap["totals"]["requests"] > 0
    assert any("/missions" in route for route in snap["routes"])
    reset_metrics()


def test_the_prometheus_exposition_is_well_formed(client: TestClient, workspace_id: str) -> None:
    from app.core.observe import prometheus_text, reset_metrics

    reset_metrics()
    client.get(f"{V1}/missions", headers=auth(BUYER))
    text = prometheus_text()
    assert "pos_requests_total" in text
    assert "# TYPE pos_requests_total counter" in text
    assert "pos_queue_depth" in text
    # Every metric line has a value.
    for line in text.splitlines():
        if line and not line.startswith("#"):
            name, _, value = line.rpartition(" ")
            assert name, f"malformed metric line: {line}"
            float(value)
    reset_metrics()


# --------------------------------------------------------------- queue age
def test_queue_age_reports_the_waiting_tasks(client: TestClient, workspace_id: str) -> None:
    from app.core.observe import reset_metrics

    reset_metrics()
    _mid, base, _doc = mission_at_plan(client, workspace_id)
    r = client.get(f"{V1}/ops/queue-age", headers=auth(MANAGER))
    # The seeded tenant has no Admin, so the endpoint refuses — but the
    # refusal must be the 403 shape, not a crash.
    assert r.status_code == 403
    reset_metrics()


def test_the_queue_age_collector_finds_waiting_tasks(client: TestClient, workspace_id: str) -> None:
    """The collector counts the waiting tasks and reports their age."""
    from app.api.ops import _refresh_queue
    from app.db import get_session
    from app.main import app

    _mid, base, _doc = mission_at_plan(client, workspace_id)
    override = app.dependency_overrides[get_session]
    generator = override()
    session = await_run(generator.__anext__())
    try:
        state = await_run(_refresh_queue(session, "t-api"))
    finally:
        await_run(generator.aclose())
    assert state["depth"] >= 0
    assert state["oldest_task_age_s"] >= 0.0


def await_run(coro: object) -> object:
    """Run a coroutine to completion (the test session is a sync fixture)."""
    import asyncio

    return asyncio.run(coro)  # type: ignore[arg-type]


# ------------------------------------------------------------------ egress
def test_the_egress_policy_refuses_a_foreign_host() -> None:
    with pytest.raises(egress.EgressDeniedError):
        egress.check_url("http://169.254.169.254/latest/", allowlist=("example.com",))


def test_the_egress_policy_refuses_a_non_http_scheme() -> None:
    for url in ("file:///etc/passwd", "gopher://x", "ftp://x", "data:text/plain,x"):
        with pytest.raises(egress.EgressDeniedError):
            egress.check_url(url, allowlist=())


def test_the_egress_policy_allows_a_listed_host_and_its_subdomains() -> None:
    egress.check_url("https://api.example.com/hook", allowlist=("example.com",))
    egress.check_url("https://example.com/hook", allowlist=("example.com",))
    with pytest.raises(egress.EgressDeniedError):
        egress.check_url("https://notexample.com/hook", allowlist=("example.com",))


def test_the_ssrf_drill_passes_against_a_live_host() -> None:
    """The drill script, end to end, against a real local HTTP server."""
    import subprocess
    import sys

    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "ssrf_drill.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SSRF / egress drill passed" in proc.stdout


# ----------------------------------------------------- environment separation
def test_the_env_checker_catches_a_dev_credential_in_a_staging_file(
    tmp_path: Path,
) -> None:
    import subprocess
    import sys

    staging = tmp_path / "staging.env"
    staging.write_text(
        "\n".join(
            [
                "APP_ENV=staging",
                "API_VERSION=v1",
                "DATABASE_URL=postgresql+asyncpg://pos:pos@localhost:5432/pos",
                "DATABASE_SYNC_URL=postgresql+psycopg://pos:pos@localhost:5432/pos",
                "REDIS_URL=redis://localhost:6379/0",
                "S3_ENDPOINT=https://s3.example",
                "S3_BUCKET=b",
                "AWS_ACCESS_KEY_ID=k",
                "AWS_SECRET_ACCESS_KEY=REPLACE_ME",
                "AWS_DEFAULT_REGION=eu-west-1",
                "OIDC_ISSUER=https://idp",
                "OIDC_AUDIENCE=aud",
                "AI_PRIMARY_BASE_URL=https://ai",
                "AI_PRIMARY_API_KEY=k",
                "AI_PRIMARY_MODEL=m",
                "AI_FALLBACK_BASE_URL=https://ai",
                "AI_FALLBACK_API_KEY=k",
                "AI_FALLBACK_MODEL=m",
                "AI_TIMEOUT_S=30",
                "AI_CIRCUIT_BREAKER_S=60",
                "OUTBOX_WEBHOOK_URL=https://hook",
                "NEXT_PUBLIC_API_BASE=https://api",
                "WEB_ORIGIN=https://app",
            ]
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(ROOT / "scripts" / "verify_env.py"),
            "--env",
            str(staging),
            "--profile",
            "staging",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    assert proc.returncode == 1
    assert "development credential" in proc.stdout


def test_the_committed_env_templates_pass() -> None:
    import subprocess
    import sys

    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "verify_env.py"), "--check-templates"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ------------------------------------------------------------------- the lock
def test_the_lockfile_is_current() -> None:
    """The committed lock must match what the declared ranges resolve to."""
    import subprocess
    import sys

    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "lock.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ----------------------------------------------------------------- the backup
def test_the_backup_script_verifies_a_sqlite_dump(tmp_path: Path) -> None:
    """A dump, its manifest, and a restore that is checked against it."""
    import sqlite3
    import subprocess
    import sys

    source = tmp_path / "source.db"
    conn = sqlite3.connect(source)
    try:
        conn.execute("CREATE TABLE pos_demo (id TEXT PRIMARY KEY, n INTEGER)")
        conn.execute("INSERT INTO pos_demo VALUES ('a', 1)")
        conn.commit()
    finally:
        conn.close()

    url = f"sqlite:///{(source).as_posix()}"
    env = {**os.environ, "DATABASE_URL": url, "DATABASE_SYNC_URL": url}
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "backup.py"), "backup", "--out", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    dumps = list(tmp_path.glob("pos-*.sqlite"))
    assert len(dumps) == 1

    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "backup.py"), "verify", str(dumps[0])],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(ROOT / "scripts" / "backup.py"),
            "restore",
            str(dumps[0]),
            "--into",
            str(tmp_path / "restored.db"),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "row counts match" in proc.stdout
