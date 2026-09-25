// P03 Intake, wired: drag-free upload with quarantine verdicts, doc queue,
// generate plan, advance to plan (intake checklist gate).
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

export default function IntakePage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [docs, setDocs] = useState<{ id: string; filename: string; status: string }[]>([]);
  const [note, setNote] = useState("");
  const [verdict, setVerdict] = useState("");

  async function load() {
    try {
      const d = await api.documents(id, readToken());
      setDocs(d.documents);
    } catch { /* denied or empty render below */ }
  }

  useEffect(() => { void load(); /* eslint-disable-next-line */ }, [id]);

  async function upload(file: File) {
    setNote(`Uploading ${file.name}…`);
    try {
      const out = await api.upload(id, file, readToken());
      setVerdict(`${file.name}: ${out.status}${out.reason ? ` — ${out.reason}` : ""}`);
      await load();
    } catch (e) {
      setVerdict(e instanceof Error ? e.message : "upload failed");
    }
  }

  async function generatePlan() {
    setNote("");
    try {
      const out = await api.generatePlan(id, readToken());
      setNote(`Plan v${out.version} proposed with ${out.tasks} tasks. Acknowledge it on the Plan screen.`);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "plan failed");
    }
  }

  const clean = docs.some((d) => d.status === "clean");

  return (
    <Screen code="P03" title="Intake" breadcrumb="Mission / Intake"
      primary="Generate plan" state={docs.length ? "success" : "empty"}>
      <label>
        Upload quote / contract (PDF, XLSX, DOCX, CSV)
        <input type="file"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void upload(f);
          }} />
      </label>
      {verdict ? <p role="status">{verdict}</p> : null}
      <table>
        <thead><tr><th>File</th><th>Status</th></tr></thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}><td>{d.filename}</td><td>{d.status}</td></tr>
          ))}
        </tbody>
      </table>
      <div className="row">
        <button type="button" disabled={!clean} onClick={() => void generatePlan()}>
          Generate plan
        </button>
      </div>
      {note ? <p role="status">{note}</p> : null}
      <AdvancePanel missionId={id} toState="plan" label="Advance to plan"
        onAdvanced={() => setNote("State: plan.")} />
    </Screen>
  );
}
