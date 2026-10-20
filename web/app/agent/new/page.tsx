// P02 Create Mission, wired: template-less 60-second creation against
// the seeded workspace list. Validation inline; submit lands on P03.
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Card, EmptyState, Field, StateBadge } from "@/components/ui";

const DIALS = [
  { value: "ASSISTED", desc: "every tool call needs human confirm" },
  { value: "SUPERVISED", desc: "auto tools run, material gated" },
  { value: "GUARDED", desc: "within caps, tighter tolerances" },
];

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
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    api.workspaces(readToken())
      .then((d) => {
        setWorkspaces(d.workspaces);
        if (d.workspaces[0]) setWs(d.workspaces[0].id);
      })
      .catch(() => {
        setWorkspaces([]);
        setDenied(true);
      });
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
      setDenied(stateForError(e) === "denied");
    }
  }

  return (
    <Screen code="P02" title="Create Mission" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "New" }]}
      primary="Create mission" state={workspaces.length ? "success" : denied ? "denied" : "empty"}>
      {workspaces.length === 0 ? (
        <EmptyState
          icon="mission"
          title="No workspace visible for this account"
          body="Connect a token on Mission Control first (demo tokens come from the synthetic seed)."
          action={{ label: "Go to Mission Control", href: "/agent" }}
        />
      ) : (
        <Card className="max-w-xl">
          <div className="gate-grid">
            <Field label="Workspace">
              <select value={ws} onChange={(e) => setWs(e.target.value)}>
                {workspaces.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </Field>
            <Field label="Title">
              <input value={title} onChange={(e) => setTitle(e.target.value)}
                placeholder="CNC Brackets Q4" />
            </Field>
            <div className="row">
              <Field label="Currency">
                <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  <option>INR</option><option>USD</option><option>EUR</option>
                </select>
              </Field>
              <Field label="Budget cap">
                <input value={budget} onChange={(e) => setBudget(e.target.value)}
                  inputMode="decimal" />
              </Field>
            </div>
            <Field label="Deadline">
              <input type="date" value={deadline}
                onChange={(e) => setDeadline(e.target.value)} />
            </Field>
            <Field label="Autonomy dial">
              <select value={dial} onChange={(e) => setDial(e.target.value)}>
                {DIALS.map((d) => (
                  <option key={d.value} value={d.value}>{d.value} — {d.desc}</option>
                ))}
              </select>
            </Field>
            <div className="row">
              <button type="button" className="primary" onClick={() => void create()}>Create mission</button>
            </div>
            {err ? <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>{err}</p> : null}
            {note ? <p role="status"><StateBadge state="ok" /> {note}</p> : null}
          </div>
        </Card>
      )}
    </Screen>
  );
}
