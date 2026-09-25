// P08 Cost Intelligence, wired: TCO ranking + build-up waterfall per supplier.
"use client";

import { use, useEffect, useState } from "react";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Cost = { supplier_id: string; tco_minor: number;
  build_up: Record<string, number>; fx: unknown[]; stale: boolean };

export default function CostPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [costs, setCosts] = useState<Cost[]>([]);
  const [state, setState] = useState<"empty" | "success" | "error">("empty");

  useEffect(() => {
    api.cost(id, readToken())
      .then((d) => {
        const rows = (d as { costs: Cost[] }).costs ?? [];
        setCosts(rows);
        setState(rows.length ? "success" : "empty");
      })
      .catch(() => setState("error"));
  }, [id]);

  const stale = costs.filter((c) => c.stale);
  return (
    <Screen code="P08" title="Cost Intelligence" breadcrumb="Mission / Cost"
      primary="Re-flag tolerances" state={state}>
      <ExceptionBanner count={stale.length}
        worst={stale.length ? `stale FX: ${stale[0].supplier_id}` : ""}
        href="#here" />
      {costs.length === 0 ? (
        <p>No TCO rows yet — run the analysis suite on the Suppliers screen.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Supplier</th><th>Price</th><th>Freight</th><th>Ins.</th>
              <th>Tooling</th><th>Tax</th><th>Disc.</th><th>TCO</th><th>FX</th>
            </tr>
          </thead>
          <tbody>
            {costs.map((c, i) => (
              <tr key={i} className={c.stale ? "stale-row" : ""}>
                <td>{c.supplier_id}</td>
                <td className="mono">{c.build_up.price}</td>
                <td className="mono">{c.build_up.freight}</td>
                <td className="mono">{c.build_up.insurance}</td>
                <td className="mono">{c.build_up.tooling}</td>
                <td className="mono">{c.build_up.tax}</td>
                <td className="mono">{c.build_up.discounts}</td>
                <td className="mono"><strong>{c.tco_minor}</strong></td>
                <td>{c.stale ? "stale" : "current"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Screen>
  );
}
