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
    primary: MockProvider, fallback: MockProvider, prompt_version: str, inputs: dict[str, Any]
) -> tuple[ProviderResult, str]:
    """Try primary, retry-once with repair, then fallback; else degraded (no fabrication)."""
    breaker = CircuitBreaker()
    first = primary.complete(prompt_version, inputs)
    if first.ok:
        return first, "ok"
    # retry-once with repair prompt
    second = primary.complete(prompt_version + "+repair", inputs)
    if second.ok:
        return second, "ok"
    breaker.record_failure()
    third = fallback.complete(prompt_version, inputs)
    if third.ok:
        return third, "degraded-fallback"
    return ProviderResult(ok=False, error=third.error or first.error, degraded=True), "degraded"
