"""Synthetic seed (brain 10 §1). ALL rows synthetic=true, codes SYNTHETIC-*.

Guards: idempotent (upsert by code/email/sku); refuses non-empty prod-flagged
DBs (any Supplier/Item/Transaction row with synthetic=false aborts).
Seed data: 7 users, 6 suppliers, 12 items, 24 transactions, document metadata
(6 quotes + 2 contracts + history + cert + HOSTILE-001/002/003), each of the
10 edge cases mapped to a test in 09_TEST_PLAN.md.

Usage: python seed/seed_pos.py --tenant SYN-TENANT-01
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

USERS = [
    ("Amara Okafor", "amara.buyer1@syn.example", "Buyer"),
    ("Luis Vega", "luis.buyer2@syn.example", "Buyer"),
    ("Priya Nair", "priya.buyer3@syn.example", "Buyer"),
    ("Daniel Roth", "daniel.manager@syn.example", "ProcurementManager"),
    ("Fatima Hassan", "fatima.finance@syn.example", "FinanceReviewer"),
    ("Chen Wei", "chen.compliance@syn.example", "ComplianceReviewer"),
    ("Seed Admin", "admin.seed@syn.example", "Admin"),
]

# Synthetic demo credential for the seeded personas (never a real secret;
# the seed refuses non-synthetic DBs).
SYN_DEMO_PASSWORD = "syn-Demo-2026!"

SUPPLIERS = [
    # code, name (sector + location), country, default incoterm, lead time (days).
    # The records are synthetic. The identifiers are opaque; the names
    # describe a sector and a location rather than naming an organisation.
    ("SYN-SUP-01", "SYN Precision Machining (Coimbatore)", "IN", "EXW", 12),
    ("SYN-SUP-02", "SYN Sheet Metal & Fabrication (Pune)", "IN", "FOB", 20),
    ("SYN-SUP-03", "SYN Castings & Forgings (Raipur)", "IN", "DDP", 15),
    ("SYN-SUP-04", "SYN Bearings & Power Transmission (Rajkot)", "IN", "CIF", 30),
    ("SYN-SUP-05", "SYN Industrial Sealants & Adhesives (Vadodara)", "IN", "DAP", 5),
    ("SYN-SUP-06", "SYN Imported Tooling (Stuttgart)", "DE", "FCA", 45),
]

ITEMS = [
    ("SYN-M6-FAST", "M6 fasteners", "fasteners", "pcs"),
    ("SYN-BRKT-A", "CNC bracket A", "brackets", "pcs"),
    ("SYN-BRKT-B", "CNC bracket B", "brackets", "pcs"),
    ("SYN-BRKT-C", "CNC bracket C", "brackets", "pcs"),
    ("SYN-SEAL-H", "Hydraulic seals", "seals", "pcs"),
    ("SYN-BUSBAR", "Copper busbars", "electrical", "pcs"),
    ("SYN-CARTON", "Packaging cartons", "packaging", "pcs"),
    ("SYN-INSERT", "Cutting inserts", "tooling", "pcs"),
    ("SYN-SENSOR", "Sensors", "electrical", "pcs"),
    ("SYN-HARNESS", "Cable harness", "electrical", "m"),
    ("SYN-PLATE", "Steel plate S355", "steel", "kg"),
    ("SYN-GASKET", "Gasket kits", "seals", "pcs"),
]

DOCUMENTS = [
    ("quote-syn-sup-01.pdf", "quote", "application/pdf"),
    ("quote-syn-sup-02.pdf", "quote", "application/pdf"),
    ("quote-syn-sup-03.pdf", "quote", "application/pdf"),
    ("quote-syn-sup-04.pdf", "quote", "application/pdf"),
    ("quote-syn-sup-05.pdf", "quote", "application/pdf"),
    ("quote-syn-sup-06.pdf", "quote", "application/pdf"),
    ("contract-syn-sup-01.pdf", "contract", "application/pdf"),
    ("contract-syn-sup-04.pdf", "contract", "application/pdf"),  # liability-shift clause
    (
        "price-history.xlsx",
        "price_history",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    ("cert-iso-9001.pdf", "cert", "application/pdf"),
    ("HOSTILE-001.pdf", "quote", "application/pdf"),  # embedded approve-X instruction
    ("HOSTILE-002.pdf", "quote", "application/pdf"),  # OCR-poisoned scan
    ("HOSTILE-003.docm", "quote", "application/pdf"),  # macro: rejected in quarantine
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed synthetic ProcurementOS-Agent data.")
    p.add_argument("--tenant", required=True, help="Tenant code, e.g. SYN-TENANT-01")
    p.add_argument("--db-url", default=os.environ.get("DATABASE_URL", ""), help="Async DB URL")
    return p.parse_args(argv)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fixture_digest(filename: str) -> tuple[int, str]:
    """The real size and SHA-256 of a seeded document's bytes.

    T15: the seeded rows used to hash the *filename*, so every document
    carried a hash that described no file. This reads the fixture the
    document claims to be and hashes those bytes. A missing fixture is a
    hard error rather than a placeholder: the seed must not invent a
    document it does not have.
    """
    path = FIXTURES / filename
    if not path.exists():
        raise FileNotFoundError(
            f"seed fixture {filename!r} is missing from {FIXTURES}; "
            "run: python seed/make_fixtures.py"
        )
    content = path.read_bytes()
    return len(content), hashlib.sha256(content).hexdigest()


async def _seed(tenant_code: str, db_url: str) -> dict[str, int]:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.auth.login import hash_password
    from app.models.base import Base
    from app.models.foundation import Document, Item, Supplier, Transaction, User, Workspace
    from app.models.mission import RuleVersion

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # create_all never ALTERs existing tables: add newer columns when
        # missing (dev convenience; staging/prod use alembic migrations).
        def _ensure_columns(sync_conn: Any) -> None:
            from sqlalchemy import inspect as sql_inspect

            cols = {c["name"] for c in sql_inspect(sync_conn).get_columns("pos_user")}
            if "password_hash" not in cols:
                sync_conn.exec_driver_sql(
                    "ALTER TABLE pos_user ADD COLUMN password_hash VARCHAR(256)"
                )

        await conn.run_sync(_ensure_columns)
    mk = async_sessionmaker(engine, expire_on_commit=False)
    counts: dict[str, int] = {
        "users": 0,
        "workspaces": 0,
        "rules": 0,
        "suppliers": 0,
        "items": 0,
        "transactions": 0,
        "documents": 0,
    }
    async with mk() as s:
        # Prod guard (T11): COUNT non-synthetic rows — inspecting one
        # arbitrary row let non-synthetic data deeper in the table through.
        from sqlalchemy import func

        for model in (Supplier, Item, Transaction):
            n_bad = (
                await s.execute(
                    select(func.count()).select_from(model).where(model.synthetic == False)  # noqa: E712
                )
            ).scalar_one()
            if n_bad:
                raise SystemExit("Refusing: non-synthetic rows present (prod-flagged DB).")
        tenant_id = tenant_code
        user_ids: dict[str, str] = {}
        # Role is used later for workspace membership; kept in the tuple.
        for name, email, _r in USERS:
            uq = await s.execute(
                select(User).where(User.tenant_id == tenant_id, User.email == email)
            )
            u = uq.scalar_one_or_none()
            if u is None:
                # B22: tokens are stored hashed — never plaintext, never
                # compared in plaintext by the API. Passwords are PBKDF2
                # (real credential login for the synthetic demo).
                u = User(
                    tenant_id=tenant_id,
                    email=email,
                    name=name,
                    api_token=hashlib.sha256(f"dev-{email}".encode()).hexdigest(),
                    password_hash=hash_password(SYN_DEMO_PASSWORD),
                )
                s.add(u)
                await s.flush()
                counts["users"] += 1
            elif (
                u.api_token != hashlib.sha256(f"dev-{email}".encode()).hexdigest()
                or not u.password_hash
            ):
                # Repair older seed runs (idempotent): plaintext tokens get
                # hashed; missing passwords get the synthetic demo password.
                u.api_token = hashlib.sha256(f"dev-{email}".encode()).hexdigest()
                if not u.password_hash:
                    u.password_hash = hash_password(SYN_DEMO_PASSWORD)
            user_ids[email] = u.id
        # One demo workspace with everyone aboard; membership is what the
        # API checks and roles come from USERS so lanes work (T14: refreshed
        # every run, not only on creation).
        wq = await s.execute(select(Workspace).where(Workspace.tenant_id == tenant_id))
        ws = wq.scalar_one_or_none()
        if ws is None:
            ws = Workspace(
                tenant_id=tenant_id,
                name="SYN Demo Workspace",
                budget_currency="INR",
                members=[],
            )
            s.add(ws)
            counts["workspaces"] += 1
            await s.flush()
        member_ids = {m.get("user_id") for m in (ws.members or [])}
        for _, email, r in USERS:
            if user_ids[email] not in member_ids:
                ws.members = list(ws.members or []) + [{"user_id": user_ids[email], "roles": [r]}]
        await s.flush()
        # T12: upsert the rule version by (tenant, version) — a bumped
        # version is never skipped just because any rule row exists.
        rq_ = await s.execute(
            select(RuleVersion).where(
                RuleVersion.tenant_id == tenant_id, RuleVersion.version == "rv-1"
            )
        )
        if rq_.scalar_one_or_none() is None:
            s.add(
                RuleVersion(
                    tenant_id=tenant_id,
                    version="rv-1",
                    effective_from="2026-01-01",
                    weights={
                        "quality": 0.25,
                        "delivery": 0.25,
                        "financial": 0.2,
                        "compliance": 0.2,
                        "geo": 0.1,
                    },
                    tolerances={
                        "fx_max_age_days": 30,
                        "award_dual_control_minor": 50_000_000,
                    },
                    fx_policy={"sources": ["RBI"], "rounding": "bankers"},
                    changelog="Initial synthetic rule set.",
                )
            )
            counts["rules"] += 1
        sup_ids: dict[str, str] = {}
        for code, name, country, _incoterm, _lead in SUPPLIERS:
            sq = await s.execute(
                select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.code == code)
            )
            sup: Supplier | None = sq.scalar_one_or_none()
            if sup is None:
                sup = Supplier(
                    tenant_id=tenant_id, code=code, name=name, country=country, synthetic=True
                )
                s.add(sup)
                await s.flush()
                counts["suppliers"] += 1
            sup_ids[code] = sup.id
        for sku, name, cat, uom in ITEMS:
            iq = await s.execute(select(Item).where(Item.tenant_id == tenant_id, Item.sku == sku))
            if iq.scalar_one_or_none() is None:
                s.add(
                    Item(
                        tenant_id=tenant_id,
                        sku=sku,
                        name=name,
                        category=cat,
                        base_uom=uom,
                        synthetic=True,
                    )
                )
                counts["items"] += 1
        # 24 transactions across 12 months; SYN-SUP-06 thin (2 txns); SYN-SUP-04
        # PPM spike. T12: re-runs top UP to 24 (deterministic by index).
        codes = [c for c, *_ in SUPPLIERS]
        existing = (
            (await s.execute(select(Transaction).where(Transaction.tenant_id == tenant_id)))
            .scalars()
            .all()
        )
        if len(existing) < 24:
            nord = sum(1 for t in existing if t.supplier_id == sup_ids["SYN-SUP-06"])
            n = len(existing)
            i = n
            while n < 24:
                code = codes[i % len(codes)]
                if code == "SYN-SUP-06":
                    if nord >= 2:
                        i += 1
                        continue  # thin-data supplier: capped at 2 txns
                    nord += 1
                defects = 40 if (code == "SYN-SUP-04" and n % 6 == 0) else (1 if n % 7 == 0 else 0)
                s.add(
                    Transaction(
                        tenant_id=tenant_id,
                        supplier_id=sup_ids[code],
                        qty=100,
                        on_time=(i % 5 != 0),
                        accepted=(i % 9 != 0),
                        defects=defects,
                        price_minor=124000 + i * 370,
                        currency="INR" if i % 3 else "USD",
                        ordered_at=datetime(2025, (i % 12) + 1, 15, tzinfo=UTC),
                        synthetic=True,
                    )
                )
                n += 1
                i += 1
            counts["transactions"] = n
        for filename, kind, mime in DOCUMENTS:
            dq = await s.execute(
                select(Document).where(
                    Document.tenant_id == tenant_id, Document.filename == filename
                )
            )
            if dq.scalar_one_or_none() is None:
                # T13: legitimate docs seed clean with real content hashes;
                # HOSTILE-* seed quarantined. HOSTILE-003 carries its true
                # macro mime, not a PDF mime.
                hostile = filename.startswith("HOSTILE-")
                true_mime = (
                    "application/vnd.ms-word.document.macroEnabled.12"
                    if filename == "HOSTILE-003.docm"
                    else mime
                )
                # T15: the hash and the size describe the real file, not the
                # filename. The fixture is read from disk and hashed as it
                # is; a document row that claims a hash no file has is a
                # lie the audit trail would repeat.
                size, sha = _fixture_digest(filename)
                s.add(
                    Document(
                        tenant_id=tenant_id,
                        mission_id="seed",
                        kind=kind,
                        filename=filename,
                        mime=true_mime,
                        size=size,
                        sha256=sha,
                        status="quarantined" if hostile else "clean",
                        synthetic=True,
                    )
                )
                counts["documents"] += 1
        await s.commit()
    await engine.dispose()
    return counts


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.tenant.startswith("SYN-"):
        print(
            "Refusing: tenant code must carry SYN- prefix (synthetic-only policy).", file=sys.stderr
        )
        return 2
    if not args.db_url:
        print(
            "seed guard ok (no --db-url: dry run). Rows would be synthetic-only.", file=sys.stderr
        )
        print(
            f"users={len(USERS)} suppliers={len(SUPPLIERS)} "
            f"items={len(ITEMS)} documents={len(DOCUMENTS)}"
        )
        return 0
    counts = asyncio.run(_seed(args.tenant, args.db_url))
    print(f"seeded {args.tenant}: " + " ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
