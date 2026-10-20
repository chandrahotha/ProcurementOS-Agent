// P04 Agent Plan, wired: current plan DAG, manager acknowledge, diff note.
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";

type Spec = { key: string; title: string; tool: string; depends_on: string[];
  estimate_min: number; autonomy_class: string };

export default function PlanPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [plan, setPlan] = useState<{ version: number; status: string; dag_hash: string } | null>(null);
  const [specs, setSpecs] = useState<Spec[]>([]);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"loading" | "success" | "empty">("loading");

  useEffect(() => {
    api.plan(id, readToken())
      .then((p) => {
        setPlan(p);
        setSpecs((p.taskspecs ?? []) as Spec[]);
        setState("success");
      })
      .catch(() => setState("empty"));
  }, [id]);

  async function acknowledge() {
    setNote("");
    if (!plan) return;
    try {
      await api.acknowledge(id, plan.version, readToken());
      setNote(`Plan v${plan.version} acknowledged.`);
      setState("success");
      const p = await api.plan(id, readToken());
      setPlan(p);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "acknowledge failed");
    }
  }

  return (
    <Screen code="P04" title="Agent Plan" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Plan" }]}
      primary={plan ? "Acknowledge plan" : undefined} onPrimary={() => void acknowledge()} state={state}>
      {state === "empty" ? (
        <EmptyState icon="plan" title="No plan yet"
          body="Generate one from the Intake screen — the DAG is validated against the closed tool registry."
          action={{ label: "Go to Intake", href: `/agent/${id}/intake` }} />
      ) : plan ? (
        <>
          <p role="status" className="row gap-2 text-sm">
            <StateBadge state={plan.status} />
            <span className="text-text-2">Version {plan.version} — {plan.status}</span>
          </p>
          <div className="table-card">
            <table>
              <caption className="sr-only">Plan tasks with tools, autonomy, and estimates</caption>
              <thead>
                <tr><th scope="col">Task</th><th scope="col">Tool</th><th scope="col">Autonomy</th><th scope="col">Deps</th><th scope="col">Est.</th></tr>
              </thead>
              <tbody>
                {specs.map((t) => (
                  <tr key={t.key}>
                    <td data-label="Task" className="font-medium">{t.title}</td>
                    <td data-label="Tool" className="mono">{t.tool}</td>
                    <td data-label="Autonomy"><StateBadge state={t.autonomy_class} /></td>
                    <td data-label="Deps" className="mono">{t.depends_on.join(", ") || "—"}</td>
                    <td data-label="Est." className="mono">{t.estimate_min}m</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row">
            <button type="button" className="primary" onClick={() => void acknowledge()}>Acknowledge plan</button>
          </div>
          {note ? <p role="status"><StateBadge state="ok" /> {note}</p> : null}
          <AdvancePanel missionId={id} toState="evidence" label="Advance to evidence"
            onAdvanced={() => setNote("State: evidence.")} />
        </>
      ) : null}
    </Screen>
  );
}
