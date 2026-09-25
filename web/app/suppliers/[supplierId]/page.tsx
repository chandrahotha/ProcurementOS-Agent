// G10 Supplier Profile, wired (F38): site, KPIs, risk history from the
// supplier profile endpoint (B48) — no longer orphaned.
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StatCard, StateBadge } from "@/components/ui";

type Profile = {
  id: string; code: string; name: string; country: string; status: string;
  site: { locale: string | null; incoterm_default: string | null; lead_time_days: number | null };
  kpis: { n: number; otd_pct: number; accept_pct: number; ppm: number; thin: boolean };
  risk_history: { composite: number; band: string; weights_version: string; at: string }[];
};

export default function SupplierProfilePage() {
  const params = useParams<{ supplierId: string }>();
  const id = params.supplierId;
  const [p, setP] = useState<Profile | null>(null);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    api.supplier(id, readToken())
      .then((d) => { setP(d); setState("success"); })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, [id]);

  const hot = p?.risk_history.filter((r) => r.band === "HIGH" || r.band === "CRITICAL") ?? [];

  return (
    <Screen code="G10" title={p ? `${p.name}` : "Supplier Profile"}
      breadcrumb={[{ label: "Suppliers", href: "/suppliers" }, { label: p?.code ?? id.slice(0, 8) }]}
      status="OTD/PPM from own transactions (thin data labeled, never inflated)" state={state}>
      {state === "empty" || state === "denied" ? (
        <EmptyState icon="suppliers" title="No such supplier"
          body="It may belong to another tenant, or the id is stale."
          action={{ label: "Back to Suppliers", href: "/suppliers" }} />
      ) : null}
      {state === "success" && p ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Transactions" value={p.kpis.n} icon="document"
              sub={p.kpis.thin ? "thin data" : "enough for KPIs"} />
            <StatCard label="OTD" value={`${p.kpis.otd_pct}%`} icon="clock" tone="ok" />
            <StatCard label="PPM" value={p.kpis.ppm} icon="alert" tone={p.kpis.ppm > 0 ? "warn" : "ok"} />
            <StatCard
              label="Latest risk"
              value={p.risk_history[0] ? p.risk_history[0].composite : "—"}
              icon="shield"
              tone={hot.length ? "bad" : "ok"}
            />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="card">
              <h2 className="card-title mb-3">Site defaults</h2>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
                <dt className="text-text-2">Locale</dt>
                <dd className="mono">{p.site.locale ?? "—"}</dd>
                <dt className="text-text-2">Incoterm</dt>
                <dd className="mono">{p.site.incoterm_default ?? "—"}</dd>
                <dt className="text-text-2">Lead time</dt>
                <dd className="mono">{p.site.lead_time_days != null ? `${p.site.lead_time_days}d` : "—"}</dd>
                <dt className="text-text-2">Country</dt>
                <dd className="mono">{p.country}</dd>
                <dt className="text-text-2">Status</dt>
                <dd><StateBadge state={p.status} /></dd>
              </dl>
            </section>
            <section>
              <h2 className="mb-3 text-sm font-semibold tracking-tight">Risk history</h2>
              <div className="table-card">
                <table>
                  <caption className="sr-only">Risk history for this supplier</caption>
                  <thead>
                    <tr><th scope="col">At</th><th scope="col">Composite</th><th scope="col">Band</th><th scope="col">Weights</th></tr>
                  </thead>
                  <tbody>
                    {p.risk_history.map((r, i) => (
                      <tr key={`${r.at}-${i}`}>
                        <td data-label="At" className="mono">{r.at.slice(0, 19)}</td>
                        <td data-label="Composite" className="mono">{r.composite}</td>
                        <td data-label="Band"><StateBadge state={r.band} /></td>
                        <td data-label="Weights" className="mono">{r.weights_version}</td>
                      </tr>
                    ))}
                    {p.risk_history.length === 0 ? (
                      <tr><td colSpan={4}>No risk rows yet — run a mission analysis.</td></tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </>
      ) : null}
    </Screen>
  );
}
