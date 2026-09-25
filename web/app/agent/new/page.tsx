// P02 Create Mission, wired: template-less 60-second creation against
// the seeded workspace list. Validation inline; submit lands on P03.
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Screen } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

export default function CreateMission() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<{ id: string; name: string }[]>([]);
  const [ws, setWs] = useState("");
  const [title, setTitle] = useState("");
  const [currency, setCurrency] = useState("EUR");
  const [budget, setBudget] = useState("100000");
  const [deadline, setDeadline] = useState("2026-12-31");
  const [dial, setDial] = useState("SUPERVISED");
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.workspaces(readToken())
      .then((d) => {
        setWorkspaces(d.workspaces);
        if (d.workspaces[0]) setWs(d.workspaces[0].id);
      })
      .catch(() => setWorkspaces([]));
  }, []);

  async function create() {
    setErr("");
    if (title.trim().length < 3) {
      setErr("Title needs at least 3 characters.");
      return;
    }
    try {
      const m = await api.createMission({
        workspace_id: ws, title, currency,
        budget_cap_minor: Math.round(Number(budget) * 100),
        deadline, autonomy_level: dial,
      }, readToken());
      setNote("Mission created.");
      router.push(`/agent/${m.id}/intake`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "create failed");
    }
  }

  return (
    <Screen code="P02" title="Create Mission" breadcrumb="Mission Control / New"
      primary="Create mission" state={workspaces.length ? "success" : "empty"}>
      {workspaces.length === 0 ? (
        <p>No workspace visible for this account. Connect a token on Mission
          Control first (demo tokens come from the synthetic seed).</p>
      ) : (
        <div className="gate-grid">
          <label>Workspace
            <select value={ws} onChange={(e) => setWs(e.target.value)}>
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </label>
          <label>Title
            <input value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="CNC Brackets Q4" />
          </label>
          <div className="row">
            <label>Currency
              <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                <option>EUR</option><option>USD</option><option>PLN</option>
              </select>
            </label>
            <label>Budget cap
              <input value={budget} onChange={(e) => setBudget(e.target.value)}
                inputMode="decimal" />
            </label>
          </div>
          <label>Deadline
            <input type="date" value={deadline}
              onChange={(e) => setDeadline(e.target.value)} />
          </label>
          <label>Autonomy dial
            <select value={dial} onChange={(e) => setDial(e.target.value)}>
              <option>ASSISTED</option>
              <option>SUPERVISED</option>
              <option>GUARDED</option>
            </select>
          </label>
          <button type="button" onClick={() => void create()}>Create mission</button>
          {err ? <p role="alert">{err}</p> : null}
          {note ? <p role="status">{note}</p> : null}
        </div>
      )}
    </Screen>
  );
}
