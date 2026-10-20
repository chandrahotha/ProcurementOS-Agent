#!/usr/bin/env python3
"""Rename the synthetic supplier identifiers and re-base the currency.

Two things happen here, and they belong together because the fixture
filenames carry the supplier codes:

1. **Identifiers.** The synthetic suppliers were named after the
   conventional placeholder trade name. A thesis artefact should not carry
   a name that reads as a placeholder, so they are replaced with opaque
   synthetic record identifiers (`SYN-SUP-01` … `SYN-SUP-06`) paired with a
   *sector and location* descriptor. The records remain synthetic and are
   marked as such; no real organisation is named.

2. **Currency.** The reporting currency becomes INR, the invoice currency
   of the domestic suppliers becomes INR, and the one imported supplier
   keeps a USD invoice so the FX path is still exercised. The FX source
   moves from the ECB to the RBI reference rate, which is the correct
   provenance for an INR/foreign-currency pair.

The script is idempotent and prints what it changed, so the migration is
reproducible rather than a one-off hand edit.

    python scripts/rename_synthetic_identifiers.py            # apply
    python scripts/rename_synthetic_identifiers.py --check    # report only
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

#: text file suffixes the rewrite touches
SUFFIXES = {".py", ".ts", ".tsx", ".md", ".json", ".yml", ".yaml", ".txt", ".csv"}

#: (old, new) pairs. Applied in order; every pair is a distinct token.
REPLACEMENTS: tuple[tuple[str, str], ...] = (
    # Supplier record identifiers.
    ("SYN-ACME", "SYN-SUP-01"),
    ("SYN-BALTIC", "SYN-SUP-02"),
    ("SYN-COBALT", "SYN-SUP-03"),
    ("SYN-DELTA", "SYN-SUP-04"),
    ("SYN-EMERALD", "SYN-SUP-05"),
    ("SYN-NORD", "SYN-SUP-06"),
    # Sector + location descriptors.
    ("SYN-Acme Industries", "SYN Precision Machining (Coimbatore)"),
    ("SYN-Baltic Components", "SYN Sheet Metal & Fabrication (Pune)"),
    ("SYN-Baltic Parts", "SYN Sheet Metal & Fabrication (Pune)"),
    ("SYN-Cobalt Works", "SYN Castings & Forgings (Raipur)"),
    ("SYN-Delta Forge", "SYN Bearings & Power Transmission (Rajkot)"),
    ("SYN-Emerald Supply", "SYN Industrial Sealants & Adhesives (Vadodara)"),
    ("SYN-Foundry Nord", "SYN Imported Tooling (Stuttgart)"),
    # Fixture filenames.
    ("quote-acme.pdf", "quote-syn-sup-01.pdf"),
    ("quote-baltic.pdf", "quote-syn-sup-02.pdf"),
    ("quote-cobalt.pdf", "quote-syn-sup-03.pdf"),
    ("quote-delta.pdf", "quote-syn-sup-04.pdf"),
    ("quote-emerald.pdf", "quote-syn-sup-05.pdf"),
    ("quote-nord.pdf", "quote-syn-sup-06.pdf"),
    ("contract-acme.pdf", "contract-syn-sup-01.pdf"),
    ("contract-delta.pdf", "contract-syn-sup-04.pdf"),
    ("cert-iso.pdf", "cert-iso-9001.pdf"),
    ("QUOTE-ACME-001", "QUOTE-SYN-SUP-01-001"),
    # Document titles.
    ("SYN-ACME FRAMEWORK AGREEMENT", "SYN-SUP-01 FRAMEWORK AGREEMENT"),
    ("SYN-DELTA FRAMEWORK AGREEMENT", "SYN-SUP-04 FRAMEWORK AGREEMENT"),
    ("SYN-COBALT ISO 9001 CERTIFICATE", "SYN-SUP-03 ISO 9001 CERTIFICATE"),
    # FX provenance for an INR/foreign-currency pair.
    ('"ECB"', '"RBI"'),
    ("ECB reference rate", "RBI reference rate"),
)

#: Fixture files that are renamed on disk.
FILE_RENAMES: tuple[tuple[str, str], ...] = (
    ("quote-acme.pdf", "quote-syn-sup-01.pdf"),
    ("quote-baltic.pdf", "quote-syn-sup-02.pdf"),
    ("quote-cobalt.pdf", "quote-syn-sup-03.pdf"),
    ("quote-delta.pdf", "quote-syn-sup-04.pdf"),
    ("quote-emerald.pdf", "quote-syn-sup-05.pdf"),
    ("quote-nord.pdf", "quote-syn-sup-06.pdf"),
    ("contract-acme.pdf", "contract-syn-sup-01.pdf"),
    ("contract-delta.pdf", "contract-syn-sup-04.pdf"),
    ("cert-iso.pdf", "cert-iso-9001.pdf"),
    ("QUOTE-ACME-001.txt", "QUOTE-SYN-SUP-01-001.txt"),
    ("QUOTE-ACME-001.pdf", "QUOTE-SYN-SUP-01-001.pdf"),
)

SKIP_DIRS = {".git", "node_modules", ".next", "__pycache__", ".kilo", ".sdlc", "backups"}


def _files() -> list[Path]:
    """Every text file to rewrite, with the noisy directories pruned.

    The walk prunes as it descends: `rglob` would still descend into
    `web/node_modules` (hundreds of thousands of files) and filter the
    result afterwards.
    """
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix in SUFFIXES:
                out.append(path)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    args = ap.parse_args(argv)

    changed = 0
    for path in _files():
        if path.resolve() == SELF:
            # This script carries the replacement table itself; rewriting it
            # would make the migration non-idempotent.
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new = text
        for old, repl in REPLACEMENTS:
            new = new.replace(old, repl)
        if new == text:
            continue
        changed += 1
        rel = path.relative_to(ROOT)
        if args.check:
            print(f"would change: {rel}")
        else:
            path.write_text(new, encoding="utf-8")
            print(f"changed: {rel}")

    fixtures = ROOT / "seed" / "fixtures"
    for old, new in FILE_RENAMES:
        src = fixtures / old
        dst = fixtures / new
        if not src.exists():
            continue
        if args.check:
            print(f"would rename: {src.name} -> {dst.name}")
        else:
            src.rename(dst)
            print(f"renamed: {src.name} -> {dst.name}")

    print(f"\n{changed} file(s) {'would be ' if args.check else ''}rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
