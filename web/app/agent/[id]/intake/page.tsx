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

type Doc = { id: string; filename: string; status: string };

/** The document queue for a mission. Module level so the effect and the
 *  reload-after-upload path share one implementation. */
async function fetchDocuments(id: string): Promise<Doc[]> {
  const d = await api.documents(id, readToken());
  return d.documents;
}

export default function IntakePage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [note, setNote] = useState("");
  const [verdict, setVerdict] = useState("");

  async function load() {
    try {
      setDocs(await fetchDocuments(id));
    } catch { /* denied or empty render below */ }
  }

  // The fetch lives inside the effect so the effect has no dependency it
  // cannot satisfy, and so a response that arrives after the screen has
  // moved on cannot overwrite the newer screen's data (F16).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const docs = await fetchDocuments(id);
        if (!cancelled) setDocs(docs);
      } catch { /* denied or empty render below */ }
    })();
    return () => { cancelled = true; };
  }, [id]);

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
