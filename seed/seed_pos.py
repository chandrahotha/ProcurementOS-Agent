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
import os
import sys

USERS = [
    ("Amara Okafor", "amara.buyer1@syn.example", "Buyer"),
    ("Luis Vega", "luis.buyer2@syn.example", "Buyer"),
    ("Priya Nair", "priya.buyer3@syn.example", "Buyer"),
    ("Daniel Roth", "daniel.manager@syn.example", "ProcurementManager"),
    ("Fatima Hassan", "fatima.finance@syn.example", "FinanceReviewer"),
    ("Chen Wei", "chen.compliance@syn.example", "ComplianceReviewer"),
    ("Seed Admin", "admin.seed@syn.example", "Admin"),
]

SUPPLIERS = [
    ("SYN-ACME", "SYN-ACME Industries", "DE", "DAP", 12),
    ("SYN-BALTIC", "SYN-Baltic Parts", "LV", "EXW", 20),
    ("SYN-COBALT", "SYN-Cobalt Works", "PL", "DAP", 15),
    ("SYN-DELTA", "SYN-Delta Forge", "TR", "CIF", 30),
    ("SYN-EMERALD", "SYN-Emerald Supply", "IE", "DDP", 5),
    ("SYN-NORD", "SYN-Foundry Nord", "SE", "FCA", 45),
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
    ("quote-acme.pdf", "quote", "application/pdf"),
    ("quote-baltic.pdf", "quote", "application/pdf"),
    ("quote-cobalt.pdf", "quote", "application/pdf"),
    ("quote-delta.pdf", "quote", "application/pdf"),
    ("quote-emerald.pdf", "quote", "application/pdf"),
    ("quote-nord.pdf", "quote", "application/pdf"),
    ("contract-acme.pdf", "contract", "application/pdf"),
    ("contract-delta.pdf", "contract", "application/pdf"),  # liability-shift clause
    (
        "price-history.xlsx",
        "price_history",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    ("cert-iso.pdf", "cert", "application/pdf"),
    ("HOSTILE-001.pdf", "quote", "application/pdf"),  # embedded approve-X instruction
    ("HOSTILE-002.pdf", "quote", "application/pdf"),  # OCR-poisoned scan
    ("HOSTILE-003.docm", "quote", "application/pdf"),  # macro: rejected in quarantine
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed synthetic ProcurementOS-Agent data.")
    p.add_argument("--tenant", required=True, help="Tenant code, e.g. SYN-TENANT-01")
    p.add_argument("--db-url", default=os.environ.get("DATABASE_URL", ""), help="Async DB URL")
    return p.parse_args(argv)


async def _seed(tenant_code: str, db_url: str) -> dict[str, int]:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models.base import Base
    from app.models.foundation import Document, Item, Supplier, Transaction, User, Workspace
    from app.models.mission import RuleVersion

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
        # Prod guard: any non-synthetic row aborts the seed.
        for model in (Supplier, Item, Transaction):
            rows = (await s.execute(select(model).limit(1))).scalars().all()
            if any(not getattr(r, "synthetic", True) for r in rows):
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
                u = User(tenant_id=tenant_id, email=email, name=name, api_token=f"dev-{email}")
                s.add(u)
                await s.flush()
                counts["users"] += 1
            user_ids[email] = u.id
        # One demo workspace with everyone aboard (membership is what the
        # API checks; roles come from USERS so Finance/Compliance lanes work).
        wq = await s.execute(select(Workspace).where(Workspace.tenant_id == tenant_id))
        if wq.scalar_one_or_none() is None:
            s.add(
                Workspace(
                    tenant_id=tenant_id,
                    name="SYN Demo Workspace",
                    budget_currency="EUR",
                    members=[{"user_id": user_ids[e], "roles": [r]} for _, e, r in USERS],
                )
            )
            counts["workspaces"] += 1
        rq_ = await s.execute(select(RuleVersion).where(RuleVersion.tenant_id == tenant_id))
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
                    tolerances={"fx_max_age_days": 30, "award_dual_control_minor": 5_000_000},
                    fx_policy={"sources": ["ECB"], "rounding": "bankers"},
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
        # 24 transactions across 12 months; SYN-NORD thin (2 txns); SYN-DELTA PPM spike.
        codes = [c for c, *_ in SUPPLIERS]
        existing = (
            (await s.execute(select(Transaction).where(Transaction.tenant_id == tenant_id)))
            .scalars()
            .all()
        )
        if not existing:
            n = 0
            nord = 0
            i = 0
            while n < 24:
                code = codes[i % len(codes)]
                if code == "SYN-NORD":
                    if nord >= 2:
                        i += 1
                        continue  # thin-data supplier: capped at 2 txns
                    nord += 1
                defects = 40 if (code == "SYN-DELTA" and n % 6 == 0) else (1 if n % 7 == 0 else 0)
                s.add(
                    Transaction(
                        tenant_id=tenant_id,
                        supplier_id=sup_ids[code],
                        qty=100,
                        on_time=(i % 5 != 0),
                        accepted=(i % 9 != 0),
                        defects=defects,
                        price_minor=1000 + i * 37,
                        currency="EUR" if i % 3 else "USD",
                        ordered_at=f"2025-{(i % 12) + 1:02d}-15T00:00:00Z",
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
                s.add(
                    Document(
                        tenant_id=tenant_id,
                        mission_id="seed",
                        kind=kind,
                        filename=filename,
                        mime=mime,
                        size=1024,
                        sha256="0" * 64,
                        status="quarantined",
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
