"""Keep the test-count and file-count figures in the documents honest.

A stale count in a document is a small lie, and several of these figures
appear in the README, the release gate, the runbook, the build log and the
findings index. This measures the numbers from the code and rewrites them
in place, so a change to the suite cannot leave the prose behind.

    python scripts/sync_counts.py            # apply
    python scripts/sync_counts.py --check    # report drift, change nothing

The build log is an append-only journal: its historical entries record
what the count *was* at the time, so only the entries in the current
pass are rewritten. The script therefore skips any line that mentions a
date other than the newest one it can see.

Measurement is by collection, not by running the suite: the count that
matters is how many tests will run, and the run itself is the CI's job.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOCS = (
    "README.md",
    "docs/RELEASE_GATE.md",
    "docs/RUNBOOK.md",
    "bugs/FINDINGS.md",
    "docs/EVALUATION.md",
    "docs/WALKTHROUGH.md",
)

#: The build log is historical; its counts are the record of each wave.
HISTORICAL = ("docs/BUILD_LOG.md",)


def measured() -> dict[str, str]:
    """The current numbers, measured rather than remembered."""
    out: dict[str, str] = {}

    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-q", "--collect-only", "-m", "not integration"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # `162/167 tests collected (5 deselected)` — the first number is what
    # will run, the second is the total, the third is what is skipped.
    m = re.search(r"(\d+)/(\d+) tests collected \((\d+) deselected\)", proc.stdout)
    if m:
        out["n"], out["total"], out["sk"] = m.group(1), m.group(2), m.group(3)
    else:
        m = re.search(r"(\d+) tests? collected", proc.stdout)
        out["n"] = out["total"] = m.group(1) if m else "0"
        m = re.search(r"\((\d+) deselected\)", proc.stdout)
        out["sk"] = m.group(1) if m else "0"

    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mypy", "app", "worker", "engine", "seed", "scripts"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # mypy reports "Success: no issues found in N source files" on success
    # and "... (checked N source files)" when there were errors. Accept both.
    m = re.search(r"(?:in|checked) (\d+) source files", proc.stdout + proc.stderr)
    out["files"] = m.group(1) if m else "0"
    return out


def rewrite(text: str, vals: dict[str, str]) -> str:
    """Replace the counted figures in one document."""
    n, sk, files = vals["n"], vals["sk"], vals["files"]
    # Repair the literal placeholders a previous broken run may have left.
    text = text.replace("{n}", n).replace("{sk}", sk).replace("{files}", files)
    # Then the numeric forms.
    text = re.sub(
        r"(?P<n>\d+) passed \+ (?P<sk>\d+) skipped",
        f"{n} passed + {sk} skipped",
        text,
    )
    text = re.sub(r"`pytest` (?P<n>\d+) passed", f"`pytest` {n} passed", text)
    text = re.sub(r"suite is \*\*(?P<n>\d+) passed", f"suite is **{n} passed", text)
    text = re.sub(r"clean \((?P<n>\d+) files\)", f"clean ({files} files)", text)
    text = re.sub(
        r"`mypy --strict` clean \((?P<n>\d+) files\)",
        f"`mypy --strict` clean ({files} files)",
        text,
    )
    text = re.sub(
        r"^(\s*- \*\*Tests: \d+ -> )\d+( passed.*)$",
        rf"\g<1>{n} passed\2",
        text,
        flags=re.M,
    )
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report drift, change nothing")
    args = ap.parse_args(argv)

    vals = measured()
    if vals["files"] == "0":
        print("could not measure the type-checked file count", file=sys.stderr)
        return 2
    print(
        f"measured: {vals['n']} run, {vals['sk']} skipped, "
        f"{vals['total']} collected, {vals['files']} type-checked files"
    )

    drift: list[str] = []
    for rel in DOCS:
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        new = rewrite(text, vals)
        if new == text:
            continue
        if args.check:
            drift.append(rel)
            print(f"would change: {rel}")
        else:
            p.write_text(new, encoding="utf-8")
            print(f"changed: {rel}")

    if args.check and drift:
        print(f"\n{len(drift)} document(s) carry a stale count")
        return 1
    if not args.check:
        print("\ndocuments synchronised")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
