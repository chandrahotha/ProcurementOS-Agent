// P09 Risk Intelligence: the weighted composite as a heatmap, plus the
// rule version that produced it.
//
// A what-if weight slider is deliberately absent: the brain asks for one,
// but a slider that recomputed a score would be a second source of truth
// next to the certified one. The weights are shown with their version
// instead, and a sandbox recomputation is a backend feature, not a
// client-side one.
"use client";

import { use, useEffect, useState } from "react";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState } from "@/components/ui";
import { Section } from "@/components/data";
import { RiskHeatmap, type RiskRow } from "@/components/intel";
import { RuleExplanation } from "@/components/panels";

type Risk = RiskRow & { weights_version: string };

type RuleVersion = {
  version: string;
  effective_from?: string;
  weights?: Record<string, unknown>;
  tolerances?: Record<string, unknown>;
  changelog?: string;
};

export default function RiskPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [rule, setRule] = useState<RuleVersion | null>(null);
  const [state, setState] = useState<"loading" | "empty" | "success" | "error" | "denied">("loading");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const d = (await api.risk(id, readToken())) as { risks: Risk[] };
        if (cancelled) return;
        const rows = d.risks ?? [];
        setRisks(rows);
        setState(rows.length ? "success" : "empty");
        // The rule version that produced these composites: the screen shows
        // the weights, not a re-computation of them.
        const rules = (await api.rules(readToken())) as { rules: RuleVersion[] };
        if (cancelled) return;
        const version = rows[0]?.weights_version;
        setRule(
          (rules.rules ?? []).find((r) => r.version === version) ??
          (rules.rules ?? [])[0] ??
          null,
        );
      } catch (e) {
        if (!cancelled) setState(stateForError(e));
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const hot = risks.filter((r) => r.band === "HIGH" || r.band === "CRITICAL");

  return (
    <Screen code="P09" title="Risk Intelligence" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Risk" }]}
      status="Weighted composite across five dimensions" state={state}>
      <ExceptionBanner count={hot.length}
        worst={hot.length ? `${hot[0]?.supplier_id ?? ""} is ${hot[0]?.band ?? ""}` : ""}
        href="#risk-heatmap" />
      {risks.length === 0 ? (
        <EmptyState icon="shield" title="No risk rows yet"
          body="Run the analysis suite on the Suppliers screen — the composite weights come from the tenant's rule version."
          action={{ label: "Go to Suppliers", href: `/agent/${id}/suppliers` }} />
      ) : (
        <>
          <Section title="Risk heatmap" id="risk-heatmap">
            <RiskHeatmap risks={risks} />
            <p className="text-xs text-text-2">
              The dimension values are <strong>risk</strong> scores: higher is
              worse, which is why the engine maps a high composite to a worse
              band. A cell shows the score the engine certified, not a
              re-computation.
            </p>
          </Section>
          {rule ? (
            <Section title="Rule version">
              <RuleExplanation
                version={rule.version}
                weights={rule.weights}
                tolerances={rule.tolerances}
                effectiveFrom={rule.effective_from}
                changelog={rule.changelog}
              />
            </Section>
          ) : null}
        </>
      )}
      <p className="text-xs text-text-2">
        Waivers need Compliance sign-off with a reason and expiry (policy
        matrix); they are never applied from this screen.
      </p>
    </Screen>
  );
}
