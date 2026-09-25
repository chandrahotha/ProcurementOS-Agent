// P03 Intake, wired: drag-free upload with quarantine verdicts, doc queue,
// generate plan, advance to plan (intake checklist gate).
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";
import { Icon } from "@/components/icons";

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
    <Screen code="P03" title="Intake" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Intake" }]}
      primary="Generate plan" onPrimary={() => void generatePlan()} state={docs.length ? "success" : "empty"}>
      <div
        className="card row justify-center gap-3 rounded-xl border-2 border-dashed p-6"
        style={{ borderColor: "var(--color-border)" }}
      >
        <span style={{ color: "var(--color-accent)" }}>
          <Icon name="upload" size={20} />
        </span>
        <label>
          Upload quote / contract (PDF, XLSX, DOCX, CSV)
          <input type="file"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void upload(f);
            }} />
        </label>
      </div>
      {verdict ? <p role="status"><StateBadge state="info" /> {verdict}</p> : null}
      {docs.length === 0 ? (
        <EmptyState icon="document" title="No documents yet"
          body="Upload a quote or contract above — the quarantine pipeline scans it and a clean verdict unlocks planning." />
      ) : (
        <div className="table-card">
          <table>
            <caption className="sr-only">Document queue with quarantine verdicts</caption>
            <thead><tr><th scope="col">File</th><th scope="col">Status</th></tr></thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td data-label="File">{d.filename}</td>
                  <td data-label="Status"><StateBadge state={d.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="row">
        <button type="button" className="primary" disabled={!clean} onClick={() => void generatePlan()}>
          Generate plan
        </button>
      </div>
      {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
      <AdvancePanel missionId={id} toState="plan" label="Advance to plan"
        onAdvanced={() => setNote("State: plan.")} />
    </Screen>
  );
}
