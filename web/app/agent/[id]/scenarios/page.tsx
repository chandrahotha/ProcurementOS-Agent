// P10 Scenario Lab, wired: manual scenarios, optimizer (Manager), list.
// No Approve button here by design (06 P10) — candidates feed negotiation.
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Scenario = { scenario_id: string; allocations: unknown[];
  objective_value: number; candidate: boolean; savings_vs_baseline: number };

export default function ScenariosPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [rows, setRows] = useState<Scenario[]>([]);
  const [demand, setDemand] = useState("100");
  const [candidate, setCandidate] = useState(true);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"empty" | "success">("empty");

  async function load() {
    try {
      const d = await api.scenariosList(id, readToken());
      setRows(d.scenarios);
      setState(d.scenarios.length ? "success" : "empty");
    } catch { setState("empty"); }
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
      const fn = optimizer ? api.optimize : api.scenario;
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
    <Screen code="P10" title="Scenario Lab" breadcrumb="Mission / Scenarios"
      primary="Mark candidate" state={state}>
      <div className="gate-grid">
        <label>Demand
          <input value={demand} onChange={(e) => setDemand(e.target.value)}
            inputMode="numeric" />
        </label>
        <label>Mark as candidate scenario
          <input type="checkbox" checked={candidate}
            onChange={(e) => setCandidate(e.target.checked)} />
        </label>
        <div className="row">
          <button type="button" onClick={() => void create(false)}>
            Create manual scenario
          </button>
          <button type="button" onClick={() => void create(true)}>
            Run optimizer (Manager)
          </button>
        </div>
        {note ? <p role="status">{note}</p> : null}
      </div>
      <table>
        <thead>
          <tr><th>Scenario</th><th>Objective</th><th>Savings vs baseline</th><th>Candidate</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.scenario_id}>
              <td className="mono">{r.scenario_id}</td>
              <td className="mono">{r.objective_value}</td>
              <td className="mono">{r.savings_vs_baseline}</td>
              <td>{r.candidate ? "yes" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <AdvancePanel missionId={id} toState="negotiation" label="Advance to negotiation (Manager)"
        onAdvanced={() => setNote("State: negotiation.")} />
    </Screen>
  );
}
