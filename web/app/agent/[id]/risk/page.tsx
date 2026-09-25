// P09 Risk Intelligence, wired: dimension scores, composite, band.
// What-if weight changes stay sandbox-only (analytical, never certified).
"use client";

import { use, useEffect, useState } from "react";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";

type Risk = { supplier_id: string; dimensions: Record<string, number>;
  composite: number; band: string; weights_version: string };

export default function RiskPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "error" | "denied">("loading");

  useEffect(() => {
    api.risk(id, readToken())
      .then((d) => {
        const rows = (d as { risks: Risk[] }).risks ?? [];
        setRisks(rows);
        setState(rows.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e)));
  }, [id]);

  const hot = risks.filter((r) => r.band === "HIGH" || r.band === "CRITICAL");
  return (
    <Screen code="P09" title="Risk Intelligence" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Risk" }]}
      status="Weighted composite across five dimensions" state={state}>
      <ExceptionBanner count={hot.length}
        worst={hot.length ? `${hot[0]?.supplier_id ?? ""} is ${hot[0]?.band ?? ""}` : ""}
        href="#risk-table" />
      {risks.length === 0 ? (
        <EmptyState icon="shield" title="No risk rows yet"
          body="Run the analysis suite on the Suppliers screen — the composite weights come from the tenant's rule version."
          action={{ label: "Go to Suppliers", href: `/agent/${id}/suppliers` }} />
      ) : (
        <div className="table-card" id="risk-table">
          <table>
            <caption className="sr-only">Risk dimensions, composite, and band per supplier</caption>
            <thead>
              <tr>
                <th scope="col">Supplier</th><th scope="col">Quality</th><th scope="col">Delivery</th><th scope="col">Fin.</th>
                <th scope="col">Compl.</th><th scope="col">Geo</th><th scope="col">Composite</th><th scope="col">Band</th><th scope="col">Weights</th>
              </tr>
            </thead>
            <tbody>
              {risks.map((r) => (
                <tr key={r.supplier_id}>
                  <td data-label="Supplier" className="font-medium">{r.supplier_id}</td>
                  <td data-label="Quality" className="mono">{r.dimensions.quality}</td>
                  <td data-label="Delivery" className="mono">{r.dimensions.delivery}</td>
                  <td data-label="Fin." className="mono">{r.dimensions.financial}</td>
                  <td data-label="Compl." className="mono">{r.dimensions.compliance}</td>
                  <td data-label="Geo" className="mono">{r.dimensions.geo}</td>
                  <td data-label="Composite" className="mono font-semibold">{r.composite}</td>
                  <td data-label="Band"><StateBadge state={r.band} /></td>
                  <td data-label="Weights" className="mono">{r.weights_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-text-2">
        Waivers need Compliance sign-off with a reason and expiry (policy
        matrix); they are never applied from this screen.
      </p>
    </Screen>
  );
}
