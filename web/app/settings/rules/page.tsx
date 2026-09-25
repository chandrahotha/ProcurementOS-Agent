// G16 Rules/Policies, wired: rule_version viewer. Weight/tolerance changes
// are dual-controlled server-side; this screen reads, it never edits.
"use client";

import { useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Rule = { version: string; effective_from: string;
  weights: Record<string, number>; tolerances: Record<string, number>;
  fx_policy: Record<string, unknown>; changelog: string };

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [state, setState] = useState<"empty" | "success" | "denied">("empty");

  useEffect(() => {
    api.rules(readToken())
      .then((d) => {
        setRules(d.rules);
        setState(d.rules.length ? "success" : "empty");
      })
      .catch(() => setState("denied"));
  }, []);

  return (
    <Screen code="G16" title="Rules & Policies" breadcrumb="Settings / Rules"
      primary="Propose change" state={state}>
      {state === "denied" ? (
        <p>Not available. Connect a token on Mission Control first.</p>
      ) : rules.length === 0 ? (
        <p>No rule versions recorded in this tenant yet.</p>
      ) : (
        rules.map((r) => (
          <section key={r.version} className="card">
            <h2 className="mono">{r.version}</h2>
            <p>Effective from {r.effective_from}. {r.changelog}</p>
            <h3>Weights</h3>
            <ul>{Object.entries(r.weights).map(([k, v]) => (
              <li key={k} className="mono">{k}: {v}</li>))}</ul>
            <h3>Tolerances</h3>
            <ul>{Object.entries(r.tolerances).map(([k, v]) => (
              <li key={k} className="mono">{k}: {v}</li>))}</ul>
            <h3>FX policy</h3>
            <pre className="mono">{JSON.stringify(r.fx_policy, null, 2)}</pre>
            <p>Past runs stay pinned to the version they were computed under;
              changes never rewrite certified results.</p>
          </section>
        ))
      )}
    </Screen>
  );
}
