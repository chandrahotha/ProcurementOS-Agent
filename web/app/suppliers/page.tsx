// G09 Suppliers Directory, wired (F37): GET /suppliers exists (B48) —
// real directory with risk bands, joined from certified results.
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";

type Supplier = { id: string; code: string; name: string; country: string;
  status: string; risk_composite: number | null; risk_band: string | null; last_rank: number | null };

export default function SuppliersDirectory() {
  const [rows, setRows] = useState<Supplier[]>([]);
  const [q, setQ] = useState("");
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    api.suppliers(readToken())
      .then((d) => {
        setRows(d.suppliers);
        setState(d.suppliers.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  const ql = q.trim().toLowerCase();
  const hits = rows.filter(
    (s) => !ql || s.name.toLowerCase().includes(ql) || s.code.toLowerCase().includes(ql) ||
      s.country.toLowerCase().includes(ql),
  );

  return (
    <Screen code="G09" title="Suppliers Directory" breadcrumb={[{ label: "Workspace" }, { label: "Suppliers" }]}
      status="Joined with the latest certified risk and sourcing results" state={state}>
      {state === "empty" ? (
        <EmptyState icon="suppliers" title="No suppliers in this tenant"
          body="Connect a token on Mission Control first (demo tokens come from the synthetic seed)."
          action={{ label: "Go to Mission Control", href: "/agent" }} />
      ) : null}
      {state === "success" ? (
        <>
          <input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Filter by name, code, or country…" aria-label="Filter suppliers"
            className="max-w-sm" />
          <div className="table-card">
            <table>
              <caption className="sr-only">Suppliers with risk bands</caption>
              <thead>
                <tr><th scope="col">Code</th><th scope="col">Name</th><th scope="col">Country</th><th scope="col">Risk</th><th scope="col">Last rank</th><th scope="col">Status</th></tr>
              </thead>
              <tbody>
                {hits.map((s) => (
                  <tr key={s.id}>
                    <td data-label="Code" className="mono">{s.code}</td>
                    <td data-label="Name">
                      <Link href={`/suppliers/${s.id}`} className="font-medium hover:text-accent">
                        {s.name}
                      </Link>
                    </td>
                    <td data-label="Country" className="mono">{s.country}</td>
                    <td data-label="Risk">
                      {s.risk_band ? (
                        <span className="row gap-2">
                          <StateBadge state={s.risk_band} />
                          <span className="mono">{s.risk_composite}</span>
                        </span>
                      ) : (
                        <span className="text-text-2">—</span>
                      )}
                    </td>
                    <td data-label="Last rank" className="mono">{s.last_rank ?? "—"}</td>
                    <td data-label="Status"><StateBadge state={s.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </Screen>
  );
}
