// P06 Evidence Center, wired: exception banner, spans table, drawer,
// quick-fill for the 8 required fields (manual entry = outage fallback),
// and the coverage-gated advance to analysis.
"use client";

import { useEffect, useState, use } from "react";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api, type Span } from "@/lib/api-client";
import { readToken } from "@/lib/token";

const REQUIRED = ["supplier", "unit_price", "currency", "uom", "quantity",
  "incoterm", "validity", "tax_mode"];

export default function EvidencePage(props: { params: Promise<{ id: string }> }) {
  const params = use(props.params);
  const mid = params.id;
  const [spans, setSpans] = useState<Span[]>([]);
  const [open, setOpen] = useState<Span | null>(null);
  const [docId, setDocId] = useState("");
  const [note, setNote] = useState("");
  const [state, setState] = useState<"loading" | "success" | "error" | "empty">("loading");

  async function load() {
    try {
      const data = await api.evidence(mid, readToken());
      setSpans(data.spans);
      setState(data.spans.length ? "success" : "empty");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mid]);

  async function quickFill() {
    setNote("");
    const docs = await api.documents(mid, readToken());
    const clean = docs.documents.find((d) => d.status === "clean");
    const target = docId || clean?.id || "manual-entry";
    try {
      const out = await api.recordSpans(mid, REQUIRED.map((f) => ({
        document_id: target, field_name: f, field_value: "12.40",
        quoted_text: `quote text ${f} (synthetic)`, confidence: 0.9,
      })), readToken());
      setNote(`${out.spans.length} spans recorded.`);
      await load();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "record failed");
    }
  }

  const flagged = spans.filter((s) => s.instruction_flag);
  const low = spans.filter((s) => !s.instruction_flag && s.confidence < 0.5);
  const covered = new Set(spans.filter((s) => !s.instruction_flag).map((s) => s.field_name));
  const pct = Math.round((REQUIRED.filter((f) => covered.has(f)).length / REQUIRED.length) * 100);
  return (
    <Screen code="P06" title="Evidence Center" breadcrumb="Mission / Evidence"
      primary="Re-run analysis" state={state}>
      <ExceptionBanner count={flagged.length + low.length}
        worst={flagged.length ? "hostile spans quarantined" : "low confidence"}
        href="#spans" />
      <p role="status">Coverage: {pct}% of required fields
        ({pct >= 80 ? "gate open" : "gate needs ≥80% or a waiver"}).</p>
      <div className="row">
        <button type="button" onClick={() => void quickFill()}>
          Quick-fill 8 required fields
        </button>
      </div>
      {note ? <p role="status">{note}</p> : null}
      <table id="spans">
        <thead>
          <tr><th>Field</th><th>Value</th><th>Conf</th><th>Flag</th><th></th></tr>
        </thead>
        <tbody>
          {spans.map((s) => (
            <tr key={s.id}>
              <td className="mono">{s.field_name}</td>
              <td>{s.field_value}</td>
              <td className="mono">{s.confidence}</td>
              <td>{s.instruction_flag ? "quarantined" : ""}</td>
              <td><button type="button" onClick={() => setOpen(s)}>Source</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <AdvancePanel missionId={mid} toState="analysis" label="Advance to analysis"
        onAdvanced={() => setNote("State: analysis.")} />
      <EvidenceDrawer missionId={mid} span={open} onClose={() => setOpen(null)}
        onCorrected={(n) => setSpans((cur) => cur.map((s) => (s.id === n.id ? n : s)))} />
    </Screen>
  );
}
