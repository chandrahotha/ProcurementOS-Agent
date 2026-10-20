"""Print the live endpoint inventory from the OpenAPI schema.

The API contract document has to match the code, and the code is the
authority. This prints the inventory so the contract can be checked
against it rather than from memory.

    python scripts/api_inventory.py
    python scripts/api_inventory.py --with-cases   # include the /cases mirror
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--with-cases", action="store_true", help="include the /cases mirror")
    args = ap.parse_args(argv)

    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./_inventory.db")
    from app.main import app

    spec = app.openapi()
    paths = [p for p in spec["paths"] if args.with_cases or "/cases/" not in p]
    for p in sorted(paths):
        methods = ",".join(sorted(m.upper() for m in spec["paths"][p]))
        summary = spec["paths"][p][sorted(spec["paths"][p])[0]].get("summary", "")
        print(f"{methods:20s} {p:56s} {summary}")
    print(f"\n{len(paths)} path(s)" + ("" if args.with_cases else " (the /cases mirror excluded)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
