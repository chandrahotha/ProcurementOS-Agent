// P08 Cost Intelligence: TCO ranking, the cost waterfall per supplier, and
// the FX provenance behind each number.
//
// The waterfall is a view, not a calculation: the segments come from the
// certified build-up the engine produced, and a stale-FX row is marked
// rather than quietly included.
"use client";

import { use, useEffect, useState } from "react";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState } from "@/components/ui";
import { DataTable, Money, Section } from "@/components/data";
import { CostWaterfall, type CostBuildUp } from "@/components/intel";

type Cost = CostBuildUp & { fx: unknown[] };

export default function CostPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [costs, setCosts] = useState<Cost[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "error" | "denied">("loading");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const d = (await api.cost(id, readToken())) as { costs: Cost[] };
        if (cancelled) return;
        const rows = d.costs ?? [];
        setCosts(rows);
        setState(rows.length ? "success" : "empty");
      } catch (e) {
        if (!cancelled) setState(stateForError(e));
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const stale = costs.filter((c) => c.stale);
  const cheapest = costs.length
    ? costs.reduce((a, b) => (a.tco_minor <= b.tco_minor ? a : b))
    : null;

  return (
    <Screen code="P08" title="Cost Intelligence" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Cost" }]}
      status="TCO build-up, price → freight → insurance → tooling → tax − discounts" state={state}>
      <ExceptionBanner count={stale.length}
        worst={stale.length ? `stale FX: ${stale[0]?.supplier_id ?? ""}` : ""}
        href="#cost-waterfall" />
      {costs.length === 0 ? (
        <EmptyState icon="chart" title="No TCO rows yet"
          body="Run the analysis suite on the Suppliers screen — the waterfall builds per supplier from certified inputs."
          action={{ label: "Go to Suppliers", href: `/agent/${id}/suppliers` }} />
      ) : (
        <>
          <Section title="Build-up" id="cost-waterfall">
            <CostWaterfall costs={costs} />
          </Section>
          <Section title="Ranking">
            <DataTable
              caption="Total cost of ownership per supplier"
              rows={costs}
              rowKey={(c) => c.supplier_id}
              initialSort={{ key: "tco", dir: "asc" }}
              columns={[
                {
                  key: "supplier",
                  header: "Supplier",
                  render: (c) => <span className="font-medium">{c.supplier_id}</span>,
                },
                {
                  key: "tco",
                  header: "TCO",
                  align: "right",
                  sortValue: (c) => c.tco_minor,
                  render: (c) => <Money minor={c.tco_minor} />,
                },
                {
                  key: "delta",
                  header: "vs cheapest",
                  align: "right",
                  sortValue: (c) => c.tco_minor - (cheapest?.tco_minor ?? 0),
                  render: (c) => {
                    const delta = c.tco_minor - (cheapest?.tco_minor ?? 0);
                    if (delta === 0) return <span className="text-text-2">—</span>;
                    return <Money minor={delta} signed />;
                  },
                },
                {
                  key: "fx",
                  header: "FX",
                  render: (c) =>
                    c.stale ? (
                      <span className="badge badge-warn">stale</span>
                    ) : Array.isArray(c.fx) && c.fx.length ? (
                      <span className="mono text-xs text-text-2">
                        {c.fx.length} source{c.fx.length > 1 ? "s" : ""}
                      </span>
                    ) : (
                      <span className="text-text-2">—</span>
                    ),
                },
              ]}
            />
          </Section>
        </>
      )}
    </Screen>
  );
}
