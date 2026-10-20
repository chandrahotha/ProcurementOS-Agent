"""The API contract document must describe the API that actually exists.

The contract is a document; a document drifts. This test reads the
OpenAPI schema — the code's own description of itself — and asserts that
every route appears in `docs/API_CONTRACT.md`. A new endpoint that is not
documented fails here, which is the point.

The `/cases/*` mirror is excluded: the contract states the rule once
rather than listing every mirrored path.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "API_CONTRACT.md"

#: The contract states the base once and writes the path relative to it,
#: abbreviates a repeated prefix with an ellipsis, and uses `{id}` where
#: the schema uses the parameter's own name. Both sides are normalised
#: onto the same spelling before they are compared.
_PARAM = re.compile(r"\{[^}]+\}")


@pytest.fixture(scope="module")
def live_paths() -> set[str]:
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./_contract.db")
    from app.main import app

    spec = app.openapi()
    return {p for p in spec["paths"] if "/cases/" not in p}


@pytest.fixture(scope="module")
def contract_text() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def _route_stem(path: str) -> str:
    """A route's identifying tail — the last two segments."""
    rel = path[len("/api/v1") :] if path.startswith("/api/v1") else path
    parts = [_PARAM.sub("{id}", p) for p in rel.split("/") if p]
    return "/".join(parts[-2:]) if len(parts) > 2 else "/".join(parts)


def _document(text: str) -> str:
    """The contract text with the parameter names normalised."""
    return _PARAM.sub("{id}", text)


def test_the_contract_file_exists() -> None:
    assert CONTRACT.exists(), "docs/API_CONTRACT.md is missing"


def test_every_live_route_is_documented(live_paths: set[str], contract_text: str) -> None:
    """Each route's path must appear in the contract."""
    documented = _document(contract_text)
    missing = [p for p in sorted(live_paths) if _route_stem(p) not in documented]
    assert not missing, f"routes not documented in API_CONTRACT.md: {missing}"


def test_the_documented_methods_match(live_paths: set[str], contract_text: str) -> None:
    """A route that lost a method must lose it in the contract too."""
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./_contract.db")
    from app.main import app

    spec = app.openapi()
    problems: list[str] = []
    for path in sorted(live_paths):
        methods = {m.upper() for m in spec["paths"][path]}
        methods.discard("HEAD")
        methods.discard("OPTIONS")
        if not methods:
            continue
        # The contract lists the method set per row; find the rows that
        # name this path and check that every method appears in one.
        tail = _route_stem(path).rsplit("/", 1)[-1]
        rows = [ln for ln in contract_text.splitlines() if ln.startswith("|") and tail in ln]
        if not rows:
            continue
        row = " ".join(rows)
        for m in methods:
            if m not in row:
                problems.append(f"{m} {path}")
    assert not problems, f"methods missing from the contract: {problems}"


def test_the_contract_states_the_cross_cutting_rules(contract_text: str) -> None:
    """The rules a client has to know."""
    assert "Idempotency-Key" in contract_text
    assert "429" in contract_text
    assert "TRUSTED_PROXY" in contract_text


def test_the_contract_names_the_base_currency(contract_text: str) -> None:
    """INR is the base currency (ADR 0011)."""
    assert "INR" in contract_text
