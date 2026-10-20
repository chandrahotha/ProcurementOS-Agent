"""B49: the AI path is in a request path, and it persists what it did.

The finding said: "AIJob/AIResult never written; run_with_fallback /
scan_output referenced only from tests — claimed AI panel/degraded-mode
marking not in any request path."

The brief endpoint does run the provider and does persist the rows, but
only when `AI_PRIMARY_BASE_URL` is configured — which is empty by default,
so the path was never exercised by any test and never showed up in the
AI-runs panel in practice. These tests configure a provider and assert:

* the brief reaches the provider and comes back with the provider's text,
* an AIJob row and an AIResult row are written for that call,
* the AI result carries the evidence refs the provider returned,
* when the provider is down the call degrades — the deterministic note
  stays, the numbers do not move, and the failure is recorded rather than
  hidden (AGENT-004),
* an unreferenced AI claim is quarantined by the hallucination scan and
  never becomes the brief's evidence note (POS-AI-HAL-01),
* the AI-runs panel reads the rows that were written.

The provider is a local stub, so no test reaches the network.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from tests.harness import BUYER, V1, auth


class _ProviderHandler(BaseHTTPRequestHandler):
    """A local stand-in for the AI provider. Never leaves the machine."""

    payload: dict = {"text": "AI note referencing certified results.", "evidence_refs": ["span-1"]}
    status: int = 200
    calls: list = []

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(length)
        type(self).calls.append(True)
        body = json.dumps({"data": type(self).payload}).encode()
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the test output clean."""


@pytest.fixture()
def provider() -> str:
    """A local AI provider; yields its base URL."""
    _ProviderHandler.payload = {
        "text": "AI note referencing certified results.",
        "evidence_refs": ["span-1"],
    }
    _ProviderHandler.status = 200
    _ProviderHandler.calls = []
    server = HTTPServer(("127.0.0.1", 0), _ProviderHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def _mission_with_result(c: TestClient, ws: str) -> str:
    """A mission with one certified cost result, so the brief has something."""
    r = c.post(
        f"{V1}/missions",
        headers=auth(BUYER),
        json={"workspace_id": ws, "title": "AI brief", "currency": "INR"},
    )
    assert r.status_code == 200, r.text
    mid = r.json()["data"]["id"]
    r = c.post(
        f"{V1}/missions/{mid}/analyze",
        headers=auth(BUYER, key="ai-analyze"),
        json={
            "modules": ["cost"],
            "quote_lines": [
                {
                    "line_id": "L1",
                    "supplier_id": "S-A",
                    "qty": "10",
                    "uom": "pcs",
                    "unit_price_minor": 100,
                    "currency": "INR",
                    "tax_mode": "exclusive",
                }
            ],
            "tco_items": [
                {
                    "supplier_id": "S-A",
                    "price_minor": 1000,
                    "freight_minor": 0,
                    "tax_minor": 0,
                    "discount_minor": 0,
                }
            ],
        },
    )
    assert r.status_code == 200, r.text
    return mid


def test_brief_persists_ai_job_and_result(
    client: TestClient, workspace_id: str, provider: str
) -> None:
    """A configured provider is called and its output is persisted."""
    old_base, old_key = settings.ai_primary_base_url, settings.ai_primary_api_key
    settings.ai_primary_base_url = provider
    settings.ai_primary_api_key = "test-key"
    try:
        mid = _mission_with_result(client, workspace_id)
        r = client.get(f"{V1}/missions/{mid}/brief", headers=auth(BUYER))
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["ai"]["ran"] is True, "the provider was never called"
        assert body["evidence_note"] == "AI note referencing certified results."
        assert _ProviderHandler.calls, "the provider received no request"
    finally:
        settings.ai_primary_base_url, settings.ai_primary_api_key = old_base, old_key


def test_ai_runs_panel_reads_the_written_rows(
    client: TestClient, workspace_id: str, provider: str
) -> None:
    """The AI-runs screen reads AIJob/AIResult — the rows the brief wrote."""
    old_base, old_key = settings.ai_primary_base_url, settings.ai_primary_api_key
    settings.ai_primary_base_url = provider
    settings.ai_primary_api_key = "test-key"
    try:
        mid = _mission_with_result(client, workspace_id)
        client.get(f"{V1}/missions/{mid}/brief", headers=auth(BUYER))

        r = client.get(f"{V1}/ai-jobs", headers=auth(BUYER))
        assert r.status_code == 200, r.text
        runs = r.json()["data"]["jobs"]
        assert runs, "the AI-runs panel is empty after a provider call"
        run = runs[0]
        assert run["purpose"] == "brief_note"
        assert run["status"] == "ok"
        assert run["mission_id"] == mid
        assert run["evidence_refs"], "the AI result carries no evidence refs"
    finally:
        settings.ai_primary_base_url, settings.ai_primary_api_key = old_base, old_key


def test_provider_outage_degrades_without_moving_the_numbers(
    client: TestClient, workspace_id: str, provider: str
) -> None:
    """AGENT-004: a dead provider degrades the note, never the certified math."""
    _ProviderHandler.status = 500
    old_base, old_key = settings.ai_primary_base_url, settings.ai_primary_api_key
    settings.ai_primary_base_url = provider
    settings.ai_primary_api_key = "test-key"
    try:
        mid = _mission_with_result(client, workspace_id)
        r = client.get(f"{V1}/missions/{mid}/brief", headers=auth(BUYER))
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["ai"]["ran"] is True
        assert body["ai"]["status"] in ("degraded", "degraded-fallback")
        # The deterministic note is still there, and the certified numbers
        # are untouched: the AI layer never becomes the source of truth.
        assert body["evidence_note"]
        assert body["winner_tco_minor"] == 1000
        assert body["ranking"][0]["tco_minor"] == 1000
    finally:
        settings.ai_primary_base_url, settings.ai_primary_api_key = old_base, old_key


def test_unreferenced_ai_claim_is_quarantined(
    client: TestClient, workspace_id: str, provider: str
) -> None:
    """POS-AI-HAL-01: a claim with no evidence ref never becomes the note."""
    _ProviderHandler.payload = {"text": "The supplier is a criminal.", "evidence_refs": []}
    old_base, old_key = settings.ai_primary_base_url, settings.ai_primary_api_key
    settings.ai_primary_base_url = provider
    settings.ai_primary_api_key = "test-key"
    try:
        mid = _mission_with_result(client, workspace_id)
        r = client.get(f"{V1}/missions/{mid}/brief", headers=auth(BUYER))
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        # The deterministic note stands in; the unreferenced claim does not.
        assert "criminal" not in body["evidence_note"]
        assert body["evidence_note"] == (
            "Every figure traces to result rows with evidence refs or a recorded waiver."
        )
        # The uncited claim is still shown, but as an uncited AI draft with
        # its citation state visible — hidden is not the same as refused.
        assert body["ai"]["cited"] is False
        assert body["ai_draft"]["cited"] is False
        assert "criminal" in body["ai_draft"]["text"]
    finally:
        settings.ai_primary_base_url, settings.ai_primary_api_key = old_base, old_key
