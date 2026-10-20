"""Scan the working tree for encoding damage.

The PowerShell `Get-Content -Raw` / `Set-Content` round-trip used to update
four documentation files mangled the UTF-8 in them: multi-byte characters
were decoded as the console's code page and written back as mojibake. This
script is the check that says whether a file is clean.

Usage:  python scripts/check_encoding.py [paths...]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".txt",
    ".json",
    ".example",
    ".cfg",
}

#: Sequences that mean "this text was decoded with the wrong code page".
#: Written as escapes so this file does not contain the very sequences it
#: is looking for.
MOJIBAKE_MARKERS = (
    "\ufffd",  # the replacement character
    "\u00e2\u20ac",  # UTF-8 em-dash read as cp1252
    "\u00c2 ",  # UTF-8 nbsp read as cp1252
    "\u00c3\u00a9",  # UTF-8 copyright read as cp1252
    "\u00d0",  # Cyrillic letter D, the classic UTF-8-as-UTF-16 artifact
)


def _git(*args: str) -> str:
    """Run a git command and return its stdout.

    The arguments are a fixed list, never anything from the repository, so
    there is no untrusted input in the call.
    """
    import shutil

    git = shutil.which("git") or "git"
    proc = subprocess.run(  # noqa: S603 - a fixed argument list
        [git, "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout


def _tracked_paths() -> list[Path]:
    """Every text file git tracks."""
    paths: list[Path] = []
    for raw in _git("ls-files", "-z").split("\0"):
        if not raw:
            continue
        p = ROOT / raw
        if p.is_file():
            paths.append(p)
    return paths


def _changed_paths() -> list[Path]:
    paths: list[Path] = []
    for line in _git("status", "--porcelain").splitlines():
        raw = line[3:].strip().strip('"')
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        p = ROOT / raw
        if p.is_dir():
            paths.extend(f for f in p.rglob("*") if f.is_file())
        elif p.is_file():
            paths.append(p)
    return paths


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"is not valid UTF-8: {exc}"]
    for marker in MOJIBAKE_MARKERS:
        if marker in text:
            problems.append(f"contains mojibake ({ascii(marker)})")
            break
    return problems


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    changed_only = "--changed" in args
    args = [a for a in args if a != "--changed"]

    if args:
        targets = [Path(a) for a in args]
    elif changed_only:
        targets = _changed_paths()
    else:
        # The default is the whole tracked tree: in CI the working tree is
        # clean, so a "changed files" check would find nothing and pass
        # without having looked at anything.
        targets = _tracked_paths()

    checked = 0
    failures = 0
    for path in targets:
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        checked += 1
        problems = check_file(path)
        if problems:
            failures += 1
            rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            for problem in problems:
                print(f"{rel}: {problem}")
    if failures:
        print(f"\n{failures} of {checked} text files have encoding problems")
        return 1
    print(f"encoding clean: {checked} text files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
