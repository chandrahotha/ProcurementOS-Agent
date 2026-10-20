"""Observability: request metrics, counters, and queue/task age.

The release gate said "OpenTelemetry wiring exists; dashboards pending
staging". It did not exist. There was no metrics, no trace, and no
dashboard — the sentence described an intention.

This is the smallest thing that is genuinely useful and carries no new
dependency:

* **Request metrics** — count, error count and duration per route, so a
  dashboard can show request rate, error rate and latency without a
  third-party agent.
* **Counters** — named events with labels (a mission advanced, an action
  executed, a task quarantined), for the same reason.
* **Queue and task age** — how many tasks are waiting and how long the
  oldest one has been waiting. A queue that stops draining is the failure
  this product is least able to notice on its own: nothing errors, the
  missions just stop moving.

The exposition format is Prometheus text, which every dashboard already
knows how to read, and it is served from `/api/v1/ops/metrics` behind an
administrator's session.

Scope is per process, the same caveat as the rate limiter: with several
workers each process counts its own share. Behind a single process (the
normal deployment for this product) the numbers are exact.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

#: A route label is the *template* ("/missions/{mission_id}"), never the
#: concrete path: a per-id label would make the metric unbounded.
MAX_ROUTES = 500
MAX_SERIES = 2_000

_lock = threading.Lock()

_requests: dict[str, dict[str, Any]] = defaultdict(
    lambda: {"count": 0, "errors": 0, "total_ms": 0.0, "max_ms": 0.0}
)
_counters: dict[tuple[str, str], int] = defaultdict(int)

#: The oldest queued task and the queue depth, refreshed by the worker
#: and by the ops endpoint.
_queue: dict[str, Any] = {"depth": 0, "oldest_task_age_s": 0.0, "updated_at": 0.0}


def _route_label(request: Any) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return str(route.path)
    return str(request.url.path)


def record_request(method: str, route: str, status: int, duration_ms: float) -> None:
    """Record one served request."""
    key = f"{method} {route}"
    with _lock:
        if key not in _requests and len(_requests) >= MAX_ROUTES:
            return
        bucket = _requests[key]
        bucket["count"] += 1
        if status >= 500:
            bucket["errors"] += 1
        bucket["total_ms"] += duration_ms
        bucket["max_ms"] = max(bucket["max_ms"], duration_ms)


def incr(name: str, labels: str = "") -> None:
    """Increment a named counter."""
    with _lock:
        key = (name, labels)
        if key not in _counters and len(_counters) >= MAX_SERIES:
            return
        _counters[key] += 1


def set_queue_state(depth: int, oldest_task_age_s: float) -> None:
    """Record the queue depth and the age of the oldest waiting task."""
    with _lock:
        _queue["depth"] = int(depth)
        _queue["oldest_task_age_s"] = float(oldest_task_age_s)
        _queue["updated_at"] = time.time()


def metrics_snapshot() -> dict[str, Any]:
    """Everything the ops endpoint reports, as plain data."""
    with _lock:
        routes = {
            key: {
                "count": v["count"],
                "errors": v["errors"],
                "avg_ms": round(v["total_ms"] / v["count"], 3) if v["count"] else 0.0,
                "max_ms": round(v["max_ms"], 3),
            }
            for key, v in _requests.items()
        }
        counters = {
            f"{name}{{{labels}}}" if labels else name: n for (name, labels), n in _counters.items()
        }
        queue = dict(_queue)
    return {
        "routes": routes,
        "counters": counters,
        "queue": queue,
        "totals": {
            "requests": sum(r["count"] for r in routes.values()),
            "errors": sum(r["errors"] for r in routes.values()),
        },
    }


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def prometheus_text() -> str:
    """The snapshot in Prometheus text exposition format."""
    snap = metrics_snapshot()
    lines: list[str] = []

    lines.append("# HELP pos_requests_total Requests served, by method and route.")
    lines.append("# TYPE pos_requests_total counter")
    for key, v in sorted(snap["routes"].items()):
        method, _, route = key.partition(" ")
        labels = f'method="{_escape(method)}",route="{_escape(route)}"'
        lines.append(f"pos_requests_total{{{labels}}} {v['count']}")

    lines.append("# HELP pos_request_errors_total Responses with a 5xx status.")
    lines.append("# TYPE pos_request_errors_total counter")
    for key, v in sorted(snap["routes"].items()):
        method, _, route = key.partition(" ")
        labels = f'method="{_escape(method)}",route="{_escape(route)}"'
        lines.append(f"pos_request_errors_total{{{labels}}} {v['errors']}")

    lines.append("# HELP pos_request_duration_ms_avg Average response time, by route.")
    lines.append("# TYPE pos_request_duration_ms_avg gauge")
    for key, v in sorted(snap["routes"].items()):
        method, _, route = key.partition(" ")
        labels = f'method="{_escape(method)}",route="{_escape(route)}"'
        lines.append(f"pos_request_duration_ms_avg{{{labels}}} {v['avg_ms']}")

    lines.append("# HELP pos_request_duration_ms_max Slowest response seen, by route.")
    lines.append("# TYPE pos_request_duration_ms_max gauge")
    for key, v in sorted(snap["routes"].items()):
        method, _, route = key.partition(" ")
        labels = f'method="{_escape(method)}",route="{_escape(route)}"'
        lines.append(f"pos_request_duration_ms_max{{{labels}}} {v['max_ms']}")

    lines.append("# HELP pos_counter Named application events.")
    lines.append("# TYPE pos_counter counter")
    for name, value in sorted(snap["counters"].items()):
        lines.append(f'pos_counter{{name="{_escape(name)}"}} {value}')

    queue = snap["queue"]
    lines.append("# HELP pos_queue_depth Tasks waiting on the queue.")
    lines.append("# TYPE pos_queue_depth gauge")
    lines.append(f"pos_queue_depth {queue.get('depth', 0)}")
    lines.append("# HELP pos_queue_oldest_task_age_seconds Age of the oldest waiting task.")
    lines.append("# TYPE pos_queue_oldest_task_age_seconds gauge")
    lines.append(f"pos_queue_oldest_task_age_seconds {queue.get('oldest_task_age_s', 0.0)}")

    return "\n".join(lines) + "\n"


def reset_metrics() -> None:
    """Clear the collected metrics (test isolation)."""
    with _lock:
        _requests.clear()
        _counters.clear()
        _queue.update({"depth": 0, "oldest_task_age_s": 0.0, "updated_at": 0.0})
