// P08 Cost Intelligence, wired: TCO ranking + build-up waterfall per supplier.
"use client";

import { use, useEffect, useState } from "react";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";

type Cost = { supplier_id: string; tco_minor: number;
  build_up: Record<string, number>; fx: unknown[]; stale: boolean };

export default function CostPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [costs, setCosts] = useState<Cost[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "error" | "denied">("loading");

  useEffect(() => {
    api.cost(id, readToken())
      .then((d) => {
        const rows = (d as { costs: Cost[] }).costs ?? [];
        setCosts(rows);
        setState(rows.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e)));
  }, [id]);

  const stale = costs.filter((c) => c.stale);
  return (
    <Screen code="P08" title="Cost Intelligence" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Cost" }]}
      status="TCO build-up, price → freight → insurance → tooling → tax − discounts" state={state}>
      <ExceptionBanner count={stale.length}
        worst={stale.length ? `stale FX: ${stale[0]?.supplier_id ?? ""}` : ""}
        href="#cost-table" />
      {costs.length === 0 ? (
        <EmptyState icon="chart" title="No TCO rows yet"
          body="Run the analysis suite on the Suppliers screen — the waterfall builds per supplier from certified inputs."
          action={{ label: "Go to Suppliers", href: `/agent/${id}/suppliers` }} />
      ) : (
        <div className="table-card" id="cost-table">
          <table>
            <caption className="sr-only">TCO build-up per supplier</caption>
            <thead>
              <tr>
                <th scope="col">Supplier</th><th scope="col">Price</th><th scope="col">Freight</th><th scope="col">Ins.</th>
                <th scope="col">Tooling</th><th scope="col">Tax</th><th scope="col">Disc.</th><th scope="col">TCO</th><th scope="col">FX</th>
              </tr>
            </thead>
            <tbody>
              {costs.map((c) => (
                <tr key={c.supplier_id} style={c.stale ? { background: "var(--color-warn-soft)" } : undefined}>
                  <td data-label="Supplier" className="font-medium">{c.supplier_id}</td>
                  <td data-label="Price" className="mono">{c.build_up.price}</td>
                  <td data-label="Freight" className="mono">{c.build_up.freight}</td>
                  <td data-label="Ins." className="mono">{c.build_up.insurance}</td>
                  <td data-label="Tooling" className="mono">{c.build_up.tooling}</td>
                  <td data-label="Tax" className="mono">{c.build_up.tax}</td>
                  <td data-label="Disc." className="mono">{c.build_up.discounts}</td>
                  <td data-label="TCO" className="mono font-semibold">{c.tco_minor}</td>
                  <td data-label="FX">{c.stale ? <StateBadge state="quarantined" /> : <StateBadge state="clean" />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Screen>
  );
}
