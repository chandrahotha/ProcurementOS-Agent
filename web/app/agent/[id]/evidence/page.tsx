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
import { Progress, StateBadge } from "@/components/ui";
import { Icon } from "@/components/icons";

const REQUIRED = ["supplier", "unit_price", "currency", "uom", "quantity",
  "incoterm", "validity", "tax_mode"];

export default function EvidencePage(props: { params: Promise<{ id: string }> }) {
  const params = use(props.params);
  const mid = params.id;
  const [spans, setSpans] = useState<Span[]>([]);
  const [open, setOpen] = useState<Span | null>(null);
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
    try {
      // The whole flow is inside the try (F21): a failure surfaces in the
      // note, never an unhandled rejection.
      const docs = await api.documents(mid, readToken());
      const clean = docs.documents.find((d) => d.status === "clean");
      const target = clean?.id || "manual-entry";
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
    <Screen code="P06" title="Evidence Center" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Evidence" }]}
      primary="Re-run analysis" state={state}>
      <ExceptionBanner count={flagged.length + low.length}
        worst={flagged.length ? "hostile spans quarantined" : "low confidence"}
        href="#spans" />
      <div className="card row flex-wrap items-center justify-between gap-3">
        <div className="row gap-3">
          <span className="text-sm font-medium text-text-2">Coverage</span>
          <span className="mono text-lg font-semibold">{pct}%</span>
          <Progress pct={pct} tone={pct >= 80 ? "ok" : "warn"} />
        </div>
        <span className="row gap-2 text-xs text-text-2">
          <Icon name={pct >= 80 ? "check" : "clock"} size={14} />
          {pct >= 80 ? "gate open" : "gate needs ≥80% or a waiver"}
        </span>
      </div>
      <div className="row">
        <button type="button" className="primary" onClick={() => void quickFill()}>
          Quick-fill 8 required fields
        </button>
      </div>
      {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
      <div className="table-card" id="spans">
        <table>
          <caption className="sr-only">Evidence spans with source drawer</caption>
          <thead>
            <tr><th scope="col">Field</th><th scope="col">Value</th><th scope="col">Conf</th><th scope="col">Flag</th><th scope="col"><span className="sr-only">Actions</span></th></tr>
          </thead>
          <tbody>
            {spans.map((s) => (
              <tr key={s.id}>
                <td data-label="Field" className="mono">{s.field_name}</td>
                <td data-label="Value">{s.field_value}</td>
                <td data-label="Conf" className="mono">{s.confidence}</td>
                <td data-label="Flag">{s.instruction_flag ? <StateBadge state="quarantined" /> : null}</td>
                <td data-label="Actions">
                  <button type="button" className="ghost text-xs" onClick={() => setOpen(s)}>Source</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <AdvancePanel missionId={mid} toState="analysis" label="Advance to analysis"
        onAdvanced={() => setNote("State: analysis.")} />
      <EvidenceDrawer missionId={mid} span={open} onClose={() => setOpen(null)}
        onCorrected={(n) => setSpans((cur) => cur.map((s) => (s.id === n.id ? n : s)))} />
    </Screen>
  );
}
