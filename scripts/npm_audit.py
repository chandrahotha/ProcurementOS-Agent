#!/usr/bin/env python3
"""The dependency-advisory gate, with a reviewed exception list.

`npm audit` exits non-zero for *any* advisory, which makes it useless as
a gate unless every advisory is actionable. This script separates the two
questions:

1. **Does the shipped artefact have an advisory?** The production
   dependency tree (`--omit=dev`) must be clean. A finding here is a
   release blocker and always fails.
2. **Does the build toolchain have an advisory?** A finding in the
   development tree fails *unless* it is on the reviewed exception list,
   which is written out below with its reason.

An exception is listed by **advisory URL**, not by package name, so a
*different* advisory affecting the same package still fails. The list is
deliberately short and every entry says why it is acceptable and when it
must be revisited.

    python scripts/npm_audit.py --prefix web
    python scripts/npm_audit.py --prefix web --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

#: Advisory URLs that are accepted in the *development* tree, with the
#: reason. Anything not on this list fails.
#
#: GHSA-vfj7-8cjw-p6xm — "braces vulnerable to stack-exhaustion denial of
#: service through deeply nested patterns", affecting every published
#: version (<= 3.0.3). It reaches us only through the lint toolchain:
#: eslint-config-next -> @next/eslint-plugin-next -> fast-glob ->
#: micromatch -> braces. There is no patched release to move to, and npm's
#: only suggestion is a major *downgrade* of eslint-config-next to 14.2.35,
#: which would drop the Next 16 lint ruleset and stop the lint gate from
#: meaning anything. The package is a build-time dependency: the runtime
#: image copies only `.next/standalone` and `.next/static`, so it is not
#: in the shipped artefact, and the exposure is a pattern the linter
#: constructs rather than untrusted input. Revisit when braces ships a
#: fix, or when the Next lint plugin stops depending on braces.
ACCEPTED_DEV_ADVISORIES: dict[str, str] = {
    "GHSA-vfj7-8cjw-p6xm": (
        "braces <= 3.0.3 (no patched release) via the eslint toolchain; "
        "dev-only, not in the runtime image"
    ),
}


def _audit(prefix: str, omit_dev: bool) -> dict[str, Any]:
    import shutil

    # On Windows npm is a shim (npm.cmd), which `shutil.which` finds.
    npm = shutil.which("npm") or "npm"
    cmd = [npm, "audit", "--prefix", prefix, "--json"]
    if omit_dev:
        cmd.append("--omit=dev")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    try:
        parsed = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return dict(parsed)


def _findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Every advisory in the report, one entry per *root* advisory.

    npm reports a vulnerability's `via` as a mix of advisory objects (the
    roots) and package names (the propagation chain). A package that
    merely depends on a vulnerable one is not a separate advisory, so
    only the object entries are counted; a string entry inherits the
    status of the root it points at.
    """
    out: list[dict[str, Any]] = []
    for name, vuln in (report.get("vulnerabilities") or {}).items():
        roots = [v for v in (vuln.get("via") or []) if not isinstance(v, str)]
        if not roots:
            # No root advisory in the report (npm sometimes reports only
            # the chain); fall back to the package's own advisory list.
            for url in vuln.get("url") or []:
                out.append(
                    {
                        "package": name,
                        "url": url,
                        "severity": vuln.get("severity", ""),
                        "title": "",
                    }
                )
            continue
        for entry in roots:
            out.append(
                {
                    "package": name,
                    "url": entry.get("url", ""),
                    "severity": entry.get("severity", vuln.get("severity", "")),
                    "title": entry.get("title", ""),
                }
            )
    return out


def _advisory_id(url: str) -> str:
    """The GHSA identifier in an advisory URL."""
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return tail if tail.startswith("GHSA-") else url


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prefix", default="web", help="the package directory")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    prod = _findings(_audit(args.prefix, omit_dev=True))
    dev = _findings(_audit(args.prefix, omit_dev=False))

    unaccepted = [f for f in dev if _advisory_id(f["url"]) not in ACCEPTED_DEV_ADVISORIES]
    accepted = [f for f in dev if _advisory_id(f["url"]) in ACCEPTED_DEV_ADVISORIES]
    accepted_report = [
        {
            "advisory": _advisory_id(f["url"]),
            "package": f["package"],
            "severity": f.get("severity", ""),
            "reason": ACCEPTED_DEV_ADVISORIES.get(_advisory_id(f["url"]), ""),
        }
        for f in accepted
    ]

    report = {
        "production": {
            "findings": prod,
            "ok": not prod,
        },
        "development": {
            "findings": unaccepted,
            "accepted": accepted_report,
            "ok": not unaccepted,
        },
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"production dependencies: {len(prod)} finding(s)")
        for f in prod:
            print(f"  BLOCKER {f['severity']:8s} {f['package']} {f['url']}")
        print(f"development dependencies: {len(unaccepted)} unaccepted, {len(accepted)} accepted")
        for f in unaccepted:
            print(f"  BLOCKER {f['severity']:8s} {f['package']} {f['url']}")
        for f in accepted_report:
            print(f"  accepted {f['advisory']} ({f['severity']}, {f['package']}) - {f['reason']}")

    if prod:
        print("\nFAILED: the shipped dependency tree has an advisory.", file=sys.stderr)
        return 1
    if unaccepted:
        print("\nFAILED: an unaccepted advisory in the development tree.", file=sys.stderr)
        return 1
    print("\ndependency gate OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
