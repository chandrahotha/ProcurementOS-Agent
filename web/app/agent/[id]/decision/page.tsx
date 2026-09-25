// P12 Decision Brief, wired: ranked recommendation, cited lines, and the
// approval request routed per the policy matrix (lanes from the server).
"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Card, EmptyState, StateBadge } from "@/components/ui";

type Brief = { winner_supplier_id: string | null; winner_tco_minor: number | null;
  ranking: { supplier_id: string; tco_minor: number }[];
  candidate_scenarios: string[];
  exceptions: { stale_fx_suppliers: string[]; lines_ranked: number };
  evidence_note: string; cited_lines: string[] };

export default function DecisionPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"loading" | "empty" | "success" | "error" | "denied">("loading");

  useEffect(() => {
    api.brief(id, readToken())
      .then((b) => { setBrief(b); setState("success"); })
      .catch((e) => setState(stateForError(e)));
  }, [id]);

  async function requestApprovals() {
    setNote("");
    // Minimal hash-locked payload: the server computes the award value from
    // certified results and picks the lanes (brain 04 §2).
    const payload = { supplier_id: brief?.winner_supplier_id ?? "S-A" };
    try {
      const out = await api.requestApprovals(id, {
        action_class: "AWARD", payload,
      }, readToken());
      setNote(`Requested: ${out.approvals.map((a) => a.lane).join(" + ")} lanes. ` +
        "Decide on the Approval screen.");
    } catch (e) {
      setNote(e instanceof Error ? e.message : "request failed");
    }
  }

  return (
    <Screen code="P12" title="Decision Brief" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Decision" }]}
      primary="Request approvals" onPrimary={() => void requestApprovals()} state={state}>
      {state === "empty" ? (
        <EmptyState icon="chart" title="No certified results yet"
          body="Run the analysis suite first — the brief ranks winners from certified TCO with cited evidence."
          action={{ label: "Go to Suppliers", href: `/agent/${id}/suppliers` }} />
      ) : brief ? (
        <>
          <p role="status" className="row flex-wrap gap-2 text-sm">
            <span className="text-text-2">Winner:</span>
            <strong className="mono text-base">{brief.winner_supplier_id ?? "—"}</strong>
            {brief.winner_tco_minor != null ? (
              <span className="mono text-text-2">at {brief.winner_tco_minor} minor units TCO</span>
            ) : null}
          </p>
          <div className="table-card">
            <table>
              <caption className="sr-only">Supplier TCO ranking</caption>
              <thead><tr><th scope="col">Supplier</th><th scope="col">TCO (minor)</th></tr></thead>
              <tbody>
                {brief.ranking.map((r) => (
                  <tr key={r.supplier_id}>
                    <td data-label="Supplier" className="font-medium">{r.supplier_id}</td>
                    <td data-label="TCO (minor)" className="mono">{r.tco_minor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Card>
            <h2 className="card-title mb-2">Evidence</h2>
            <ul className="row list-none flex-col gap-1.5 p-0 text-sm">
              {brief.cited_lines.map((l, i) => (
                <li key={`${l}-${i}`} className="row gap-2">
                  <StateBadge state="ok" />
                  <span>{l}</span>
                </li>
              ))}
            </ul>
            <p className="mono mt-3 text-xs text-text-2">{brief.evidence_note}</p>
          </Card>
          <div className="row">
            <button type="button" className="primary" onClick={() => void requestApprovals()}>
              Request approvals
            </button>
            <Link href={`/agent/${id}/approval`}>Go to Approval</Link>
          </div>
          {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
        </>
      ) : null}
    </Screen>
  );
}
