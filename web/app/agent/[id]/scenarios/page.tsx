// P10 Scenario Lab, wired: manual scenarios, optimizer (Manager), list.
// No Approve button here by design (06 P10) — candidates feed negotiation.
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Card, EmptyState, Field, StateBadge } from "@/components/ui";

type Scenario = { scenario_id: string; allocations: unknown[];
  objective_value: number; candidate: boolean; savings_vs_baseline: number };

export default function ScenariosPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [rows, setRows] = useState<Scenario[]>([]);
  const [demand, setDemand] = useState("100");
  const [candidate, setCandidate] = useState(true);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"loading" | "empty" | "success" | "error" | "denied">("loading");

  async function load() {
    try {
      const d = await api.scenariosList(id, readToken());
      setRows(d.scenarios);
      setState(d.scenarios.length ? "success" : "empty");
    } catch (e) { setState(stateForError(e)); }
  }

  useEffect(() => { void load(); /* eslint-disable-next-line */ }, [id]);

  const offers = [
    { supplier_id: "S-A", unit_cost_minor: 50, capacity: 60 },
    { supplier_id: "S-B", unit_cost_minor: 60, capacity: 60 },
  ];

  async function create(optimizer: boolean) {
    setNote("");
    const body = { scenario_id: optimizer ? `opt-${Date.now()}` : `man-${Date.now()}`,
      demand: Number(demand), offers, candidate };
    try {
      const out = optimizer
        ? await api.optimize(id, body, readToken())
        : await api.scenario(id, body, readToken());
      setNote(`${out.scenario_id}: objective ${out.objective_value}, ` +
        `savings ${out.savings_vs_baseline} vs baseline.`);
      await load();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "scenario failed");
    }
  }

  return (
    <Screen code="P10" title="Scenario Lab" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Scenarios" }]}
      status="Least-cost allocation; candidates feed negotiation" state={state}>
      <Card className="max-w-xl">
        <div className="gate-grid">
          <div className="row">
            <Field label="Demand">
              <input value={demand} onChange={(e) => setDemand(e.target.value)}
                inputMode="numeric" />
            </Field>
            <label className="row items-center gap-2 pt-6 text-xs font-medium">
              <input type="checkbox" checked={candidate} className="h-4 w-4"
                onChange={(e) => setCandidate(e.target.checked)} />
              Mark as candidate scenario
            </label>
          </div>
          <div className="row">
            <button type="button" onClick={() => void create(false)}>
              Create manual scenario
            </button>
            <button type="button" className="primary" onClick={() => void create(true)}>
              Run optimizer (Manager)
            </button>
          </div>
          {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
        </div>
      </Card>
      {rows.length === 0 ? (
        <EmptyState icon="chart" title="No scenarios yet"
          body="Create a manual scenario or run the optimizer — the greedy allocator is capacity-aware and certified." />
      ) : (
        <div className="table-card">
          <table>
            <caption className="sr-only">Scenarios with objective and savings</caption>
            <thead>
              <tr><th scope="col">Scenario</th><th scope="col">Objective</th><th scope="col">Savings vs baseline</th><th scope="col">Candidate</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.scenario_id}>
                  <td data-label="Scenario" className="mono">{r.scenario_id}</td>
                  <td data-label="Objective" className="mono">{r.objective_value}</td>
                  <td data-label="Savings vs baseline" className="mono">{r.savings_vs_baseline}</td>
                  <td data-label="Candidate">{r.candidate ? <StateBadge state="ok" /> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <AdvancePanel missionId={id} toState="negotiation" label="Advance to negotiation (Manager)"
        onAdvanced={() => setNote("State: negotiation.")} />
    </Screen>
  );
}
