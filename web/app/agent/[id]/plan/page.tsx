// P04 Agent Plan, wired: current plan DAG, manager acknowledge, diff note.
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

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
    try {
      await api.acknowledge(id, plan!.version, readToken());
      setNote(`Plan v${plan!.version} acknowledged.`);
      setState("success");
      const p = await api.plan(id, readToken());
      setPlan(p);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "acknowledge failed");
    }
  }

  return (
    <Screen code="P04" title="Agent Plan" breadcrumb="Mission / Plan"
      primary="Acknowledge plan" state={state}>
      {state === "empty" ? (
        <p>No plan yet — generate one from the Intake screen.</p>
      ) : plan ? (
        <>
          <p role="status">Version {plan.version} — {plan.status}</p>
          <table>
            <thead>
              <tr><th>Task</th><th>Tool</th><th>Autonomy</th><th>Deps</th><th>Est.</th></tr>
            </thead>
            <tbody>
              {specs.map((t) => (
                <tr key={t.key}>
                  <td>{t.title}</td>
                  <td className="mono">{t.tool}</td>
                  <td>{t.autonomy_class}</td>
                  <td>{t.depends_on.join(", ") || "—"}</td>
                  <td className="mono">{t.estimate_min}m</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row">
            <button type="button" onClick={() => void acknowledge()}>Acknowledge plan</button>
          </div>
          {note ? <p role="status">{note}</p> : null}
          <AdvancePanel missionId={id} toState="evidence" label="Advance to evidence"
            onAdvanced={() => setNote("State: evidence.")} />
        </>
      ) : null}
    </Screen>
  );
}
