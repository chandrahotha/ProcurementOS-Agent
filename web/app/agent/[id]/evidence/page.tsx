// P06 Evidence Center, wired: exception banner, spans table, drawer.
"use client";

import { useEffect, useState } from "react";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { api, type Span } from "@/lib/api-client";
import { readToken } from "@/lib/token";

export default function EvidencePage({ params }: { params: { id: string } }) {
  const mid = params.id;
  const [spans, setSpans] = useState<Span[]>([]);
  const [open, setOpen] = useState<Span | null>(null);
  const [state, setState] = useState<"loading" | "success" | "error">("loading");

  async function load() {
    try {
      const data = await api.evidence(mid, readToken());
      setSpans(data.spans);
      setState("success");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mid]);

  const flagged = spans.filter((s) => s.instruction_flag);
  const low = spans.filter((s) => !s.instruction_flag && s.confidence < 0.5);
  return (
    <Screen code="P06" title="Evidence Center" breadcrumb="Mission / Evidence"
      primary="Re-run analysis" state={state}>
      <ExceptionBanner count={flagged.length + low.length}
        worst={flagged.length ? "hostile spans quarantined" : "low confidence"}
        href="#spans" />
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
      <EvidenceDrawer missionId={mid} span={open} onClose={() => setOpen(null)}
        onCorrected={(n) => setSpans((cur) => cur.map((s) => (s.id === n.id ? n : s)))} />
    </Screen>
  );
}
