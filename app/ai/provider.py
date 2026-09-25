"""AI provider abstraction: primary + fallback, structured JSON only, outage fallback.

AGENT-004 contract: provider timeout/5xx/auth-fail/schema-fail-twice ->
circuit breaker -> run `degraded`: deterministic engine unaffected, AI panels
show unavailable cards, drafts disabled with reason, mission continues to
approval/report. Recovery replays the queue without recomputing math.
No fabricated placeholder text is ever rendered as AI output.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ProviderResult:
    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    degraded: bool = False


class MockProvider:
    """Test/CI double with outage toggle (mirrors compose mock-ai)."""

    def __init__(self, down: bool = False, fail_schema_times: int = 0):
        self.down = down
        self.fail_schema_times = fail_schema_times
        self.calls = 0

    def complete(self, prompt_version: str, inputs: dict[str, Any]) -> ProviderResult:
        self.calls += 1
        if self.down:
            return ProviderResult(ok=False, error="provider_down", degraded=True)
        if self.fail_schema_times > 0:
            self.fail_schema_times -= 1
            return ProviderResult(ok=False, error="schema_invalid", degraded=True)
        return ProviderResult(
            ok=True,
            payload={
                "text": "Cited explanation of certified results.",
                "evidence_refs": ["span-1"],
                "prompt_version": prompt_version,
            },
        )


class HttpxProvider:
    """Real provider: POSTs to the configured AI endpoint (server-side only,
    never from the browser). Schema-strict: non-dict payloads are invalid."""

    def __init__(self, base_url: str, api_key: str = "", model: str = "", timeout_s: int = 30):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    def complete(self, prompt_version: str, inputs: dict[str, Any]) -> ProviderResult:
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            r = httpx.post(
                f"{self.base_url}/completions",
                json={"model": self.model, "prompt_version": prompt_version, "inputs": inputs},
                headers=headers,
                timeout=self.timeout_s,
            )
            if r.status_code >= 300:
                return ProviderResult(
                    ok=False, error=f"provider_http_{r.status_code}", degraded=True
                )
            body = r.json()
            payload = body.get("data") if isinstance(body, dict) else None
            if not isinstance(payload, dict):
                return ProviderResult(ok=False, error="schema_invalid", degraded=True)
            return ProviderResult(
                ok=True,
                payload={
                    "text": str(payload.get("text", "")),
                    "evidence_refs": list(payload.get("evidence_refs", [])),
                    "prompt_version": prompt_version,
                    "model": self.model or str(payload.get("model", "")),
                },
            )
        except Exception as e:
            return ProviderResult(ok=False, error=f"provider_unreachable: {e}", degraded=True)


@dataclass
class CircuitBreaker:
    failures: int = 0
    opened_until: float = 0.0
    backoff_s: float = 60.0

    def tripped(self) -> bool:
        return time.time() < self.opened_until

    def record_failure(self) -> None:
        self.failures += 1
        self.opened_until = time.time() + self.backoff_s

    def record_success(self) -> None:
        self.failures = 0
        self.opened_until = 0.0


def run_with_fallback(
    primary: MockProvider | HttpxProvider,
    fallback: MockProvider | HttpxProvider,
    prompt_version: str,
    inputs: dict[str, Any],
    breaker: CircuitBreaker | None = None,
) -> tuple[ProviderResult, str]:
    """Try primary, retry-once with repair, then fallback; else degraded (no fabrication).

    The circuit breaker is persistent (per process, or passed in): once it
    trips, calls skip straight to the fallback for the cooldown window
    instead of pointlessly retrying a down provider (B6).
    """
    from app.core.config import settings

    br = breaker or _BREAKER
    if br.backoff_s != float(settings.ai_circuit_breaker_s) and breaker is not None:
        br.backoff_s = float(settings.ai_circuit_breaker_s)
    if br.tripped():
        third = fallback.complete(prompt_version, inputs)
        if third.ok:
            br.record_success()
            return third, "degraded-fallback"
        return ProviderResult(ok=False, error=third.error, degraded=True), "degraded"
    first = primary.complete(prompt_version, inputs)
    if first.ok:
        br.record_success()
        return first, "ok"
    # retry-once with repair prompt
    second = primary.complete(prompt_version + "+repair", inputs)
    if second.ok:
        br.record_success()
        return second, "ok"
    br.record_failure()
    third = fallback.complete(prompt_version, inputs)
    if third.ok:
        br.record_success()
        return third, "degraded-fallback"
    return ProviderResult(ok=False, error=third.error or first.error, degraded=True), "degraded"


_BREAKER = CircuitBreaker()
