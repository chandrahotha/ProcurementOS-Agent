// P09 Risk Intelligence, wired: dimension scores, composite, band.
// What-if weight changes stay sandbox-only (analytical, never certified).
"use client";

import { use, useEffect, useState } from "react";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Risk = { supplier_id: string; dimensions: Record<string, number>;
  composite: number; band: string; weights_version: string };

export default function RiskPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [state, setState] = useState<"empty" | "success" | "error">("empty");

  useEffect(() => {
    api.risk(id, readToken())
      .then((d) => {
        const rows = (d as { risks: Risk[] }).risks ?? [];
        setRisks(rows);
        setState(rows.length ? "success" : "empty");
      })
      .catch(() => setState("error"));
  }, [id]);

  const hot = risks.filter((r) => r.band === "HIGH" || r.band === "CRITICAL");
  return (
    <Screen code="P09" title="Risk Intelligence" breadcrumb="Mission / Risk"
      primary="Request waiver" state={state}>
      <ExceptionBanner count={hot.length}
        worst={hot.length ? `${hot[0].supplier_id} is ${hot[0].band}` : ""}
        href="#here" />
      {risks.length === 0 ? (
        <p>No risk rows yet — run the analysis suite on the Suppliers screen.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Supplier</th><th>Quality</th><th>Delivery</th><th>Fin.</th>
              <th>Compl.</th><th>Geo</th><th>Composite</th><th>Band</th><th>Weights</th>
            </tr>
          </thead>
          <tbody>
            {risks.map((r) => (
              <tr key={r.supplier_id}>
                <td>{r.supplier_id}</td>
                <td className="mono">{r.dimensions.quality}</td>
                <td className="mono">{r.dimensions.delivery}</td>
                <td className="mono">{r.dimensions.financial}</td>
                <td className="mono">{r.dimensions.compliance}</td>
                <td className="mono">{r.dimensions.geo}</td>
                <td className="mono">{r.composite}</td>
                <td>{r.band}</td>
                <td className="mono">{r.weights_version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p>Waivers need Compliance sign-off with a reason and expiry (policy
        matrix); they are never applied from this screen.</p>
    </Screen>
  );
}
