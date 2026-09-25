// P07 Supplier Intelligence, wired: run the native suite (idempotent) and
// read sourcing rankings. KPIs come back in the run summary (OTD/PPM).
"use client";

import { use, useEffect, useState } from "react";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

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
    normalized_total_minor: number; rank: number; compliant: boolean }[]>([]);
  const [kpis, setKpis] = useState<Record<string, unknown> | null>(null);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"empty" | "success">("empty");

  useEffect(() => {
    api.sourcing(id, readToken())
      .then((d) => {
        setLines((d as { lines: typeof lines }).lines ?? []);
        if ((d as { lines: typeof lines }).lines?.length) setState("success");
      })
      .catch(() => setState("empty"));
  }, [id]);

  async function run() {
    setNote("");
    try {
      const out = await api.analyze(id, DEMO_PAYLOAD, readToken(),
        `web-${id}-analyze`);
      setNote(`Run ${out.run_id}${out.replayed ? " (replayed)" : ""} complete.`);
      const d = (await api.sourcing(id, readToken())) as { lines: typeof lines };
      setLines(d.lines ?? []);
      setState("success");
    } catch (e) {
      setNote(e instanceof Error ? e.message : "analysis failed");
    }
  }

  return (
    <Screen code="P07" title="Supplier Intelligence" breadcrumb="Mission / Suppliers"
      primary="Run analysis" state={state}>
      <ExceptionBanner count={0} worst="" href="#here" />
      <div className="row">
        <button type="button" onClick={() => void run()}>
          Run native analysis suite
        </button>
      </div>
      {note ? <p role="status">{note}</p> : null}
      {kpis ? <pre className="mono">{JSON.stringify(kpis, null, 2)}</pre> : null}
      <table>
        <thead>
          <tr><th>Line</th><th>Supplier</th><th>Total (minor)</th><th>Rank</th><th>Compliant</th></tr>
        </thead>
        <tbody>
          {lines.map((l, i) => (
            <tr key={i}>
              <td className="mono">{l.line_id}</td>
              <td>{l.supplier_id}</td>
              <td className="mono">{l.normalized_total_minor}</td>
              <td className="mono">{l.rank}</td>
              <td>{l.compliant ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <AdvancePanel missionId={id} toState="scenarios" label="Advance to scenarios"
        onAdvanced={() => setNote("State: scenarios.")} />
    </Screen>
  );
}
