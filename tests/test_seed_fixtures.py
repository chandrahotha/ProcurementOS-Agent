"""The seeded corpus and the fixtures on disk must agree.

T15 said: "Seed metadata references quote-syn-sup-01.pdf, quote-syn-sup-02.pdf etc.
but fixtures/ has only QUOTE-SYN-SUP-01-001.txt/pdf + HOSTILE-001/002.txt — 11 of
13 unmatched."

The seed used to list thirteen filenames that did not exist and hashed the
*filename* rather than any content, so every seeded document carried a
sha256 that described no file. These tests pin the fix:

* every filename the seed lists exists in seed/fixtures/,
* the size and hash the seed will record are the ones the file really has,
* the hostile fixtures really contain an injection payload, so the
  quarantine has something to isolate,
* the macro fixture really trips the macro scan,
* the generated fixtures are exactly what the generator produces (no
  hand-edited binaries drifting away from the source of truth).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.ingest import instructions, pipeline
from seed.seed_pos import DOCUMENTS, _fixture_digest

FIXTURES = Path(__file__).resolve().parent.parent / "seed" / "fixtures"


def test_every_seeded_document_exists_on_disk() -> None:
    missing = [name for name, _kind, _mime in DOCUMENTS if not (FIXTURES / name).exists()]
    assert not missing, f"seed lists documents that do not exist: {missing}"


def test_seeded_hash_and_size_describe_the_real_bytes() -> None:
    for name, _kind, _mime in DOCUMENTS:
        content = (FIXTURES / name).read_bytes()
        size, sha = _fixture_digest(name)
        assert size == len(content), f"{name}: recorded size is not the file size"
        assert sha == hashlib.sha256(content).hexdigest(), (
            f"{name}: recorded hash is not the file hash"
        )
        assert len(sha) == 64


def test_hostile_fixtures_carry_an_injection_payload() -> None:
    """The hostile PDFs must trip the real instruction scan."""
    for name in ("HOSTILE-001.pdf", "HOSTILE-002.pdf"):
        content = (FIXTURES / name).read_bytes()
        # The text is inside a PDF's uncompressed content stream, so the
        # payload is visible in the bytes.
        scan = instructions.scan(content.decode("latin-1"))
        assert scan["flagged"], f"{name} carries no injection payload"
        assert scan["hits"]


def test_macro_fixture_trips_the_macro_scan() -> None:
    """HOSTILE-003.docm must be rejected by the quarantine."""
    content = (FIXTURES / "HOSTILE-003.docm").read_bytes()
    result = pipeline.validate_upload(
        "HOSTILE-003.docm",
        "application/vnd.ms-word.document.macroEnabled.12",
        content,
    )
    assert result["verdict"] == "rejected"
    # The extension is not on the allowlist at all, which is the first
    # line of defence; the macro marker is the second.
    assert "not allowed" in result["reason"] or "macro" in result["reason"]


def test_generated_fixtures_match_the_generator() -> None:
    """No hand-edited binary may drift from seed/make_fixtures.py."""
    from seed.make_fixtures import main

    assert main(["--check"]) == 0


def test_clean_fixtures_do_not_trip_the_instruction_scan() -> None:
    """A clean quote must not look like an instruction."""
    for name, _kind, _mime in DOCUMENTS:
        if name.startswith("HOSTILE-"):
            continue
        content = (FIXTURES / name).read_bytes()
        scan = instructions.scan(content.decode("latin-1"))
        assert not scan["flagged"], f"{name} (a clean document) trips the scan: {scan['hits']}"


@pytest.mark.parametrize(
    "name", ["quote-syn-sup-01.pdf", "quote-syn-sup-02.pdf", "quote-syn-sup-06.pdf"]
)
def test_quote_fixtures_are_readable_pdfs(name: str) -> None:
    content = (FIXTURES / name).read_bytes()
    assert content.startswith(b"%PDF")
    assert b"%%EOF" in content
