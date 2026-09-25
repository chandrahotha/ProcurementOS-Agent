// P07 Supplier Intelligence, wired: run the native suite (idempotent) and
// read sourcing rankings + run KPIs from the analysis summary (F6).
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";

const DEMO_PAYLOAD = {
  modules: ["sourcing", "supplier", "cost", "risk"],
  target_currency: "EUR", base_uom: "pcs",
  quote_lines: [
    { line_id: "L1", supplier_id: "S-A", qty: "48", uom: "pcs",
      unit_price_minor: 90, currency: "EUR", tax_mode: "inclusive" },
    { line_id: "L1", supplier_id: "S-B", qty: "2", uom: "box",
      unit_price_minor: 1000, currency: "USD", tax_mode: "exclusive",
      tax_rate: "0.19",
      fx: { pair: "USD/EUR", rate: "0.92", source: "ECB",
        quoted_at: "2026-09-01T00:00:00Z" } },
  ],
  transactions: [{ on_time: true, accepted: true, qty: 100, defects: 1 }],
  tco_items: [
    { supplier_id: "S-A", price_minor: 4320, freight_minor: 200,
      tax_minor: 300, discount_minor: 100 },
  ],
  risk: { suppliers: { "S-A": { quality: 10, delivery: 10, financial: 10,
    compliance: 10, geo: 10 } } },
};

export default function SuppliersPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [lines, setLines] = useState<{ line_id: string; supplier_id: string;
    normalized_total_minor: number; rank: number; compliant: boolean; evidence_refs: string[] }[]>([]);
  const [kpis, setKpis] = useState<Record<string, unknown> | null>(null);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"loading" | "empty" | "success" | "error" | "denied">("loading");

  useEffect(() => {
    api.sourcing(id, readToken())
      .then((d) => {
        setLines((d as { lines: typeof lines }).lines ?? []);
        setState((d as { lines: typeof lines }).lines?.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e)));
  }, [id]);

  async function run() {
    setNote("");
    try {
      const out = await api.analyze(id, DEMO_PAYLOAD, readToken(),
        `web-${id}-analyze`);
      setNote(`Run ${out.run_id}${out.replayed ? " (replayed)" : ""} complete.`);
      // Run KPIs come back in the analyze summary (F6): supplier_kpis.
      const summary = out as unknown as { supplier_kpis?: Record<string, unknown> };
      if (summary.supplier_kpis) setKpis(summary.supplier_kpis);
      const d = (await api.sourcing(id, readToken())) as { lines: typeof lines };
      setLines(d.lines ?? []);
      setState("success");
    } catch (e) {
      setNote(e instanceof Error ? e.message : "analysis failed");
    }
  }

  return (
    <Screen code="P07" title="Supplier Intelligence" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Suppliers" }]}
      status="Sourcing rankings from certified runs" state={state}>
      <div className="row">
        <button type="button" className="primary" onClick={() => void run()}>
          Run native analysis suite
        </button>
      </div>
      {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
      {kpis ? (
        <div className="card row flex-wrap gap-4 text-sm">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-2">Run KPIs</span>
          {Object.entries(kpis).map(([k, v]) => (
            <span key={k} className="mono">
              {k}: <strong>{String(v)}</strong>
            </span>
          ))}
        </div>
      ) : null}
      {state === "empty" ? (
        <EmptyState icon="suppliers" title="No sourcing results yet"
          body="Run the native analysis suite — sourcing, supplier KPIs, TCO, and risk compute deterministically and persist as certified rows." />
      ) : state === "success" ? (
        <div className="table-card">
          <table>
            <caption className="sr-only">Sourcing rankings per supplier</caption>
            <thead>
              <tr><th scope="col">Line</th><th scope="col">Supplier</th><th scope="col">Total (minor)</th><th scope="col">Rank</th><th scope="col">Compliant</th></tr>
            </thead>
            <tbody>
              {lines.map((l) => (
                <tr key={`${l.line_id}-${l.supplier_id}`}>
                  <td data-label="Line" className="mono">{l.line_id}</td>
                  <td data-label="Supplier" className="font-medium">{l.supplier_id}</td>
                  <td data-label="Total (minor)" className="mono">{l.normalized_total_minor}</td>
                  <td data-label="Rank" className="mono">{l.rank === 0 ? "—" : l.rank}</td>
                  <td data-label="Compliant">{l.compliant ? <StateBadge state="ok" /> : <StateBadge state="bad" />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <AdvancePanel missionId={id} toState="scenarios" label="Advance to scenarios"
        onAdvanced={() => setNote("State: scenarios.")} />
    </Screen>
  );
}
