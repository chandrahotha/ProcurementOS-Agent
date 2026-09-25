// P12 Decision Brief, wired: ranked recommendation, cited lines, and the
// approval request routed per the policy matrix (lanes from the server).
"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Screen } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Brief = { winner_supplier_id: string | null; winner_tco_minor: number | null;
  ranking: { supplier_id: string; tco_minor: number }[];
  candidate_scenarios: string[];
  exceptions: { stale_fx_suppliers: string[]; lines_ranked: number };
  evidence_note: string; cited_lines: string[] };

export default function DecisionPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"empty" | "success" | "error">("empty");

  useEffect(() => {
    api.brief(id, readToken())
      .then((b) => { setBrief(b); setState("success"); })
      .catch(() => setState("empty"));
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
    <Screen code="P12" title="Decision Brief" breadcrumb="Mission / Decision"
      primary="Request approvals" state={state}>
      {state === "empty" ? (
        <p>No certified results yet — run the analysis suite first.</p>
      ) : brief ? (
        <>
          <p role="status">
            Winner: <strong>{brief.winner_supplier_id ?? "—"}</strong>
            {brief.winner_tco_minor != null
              ? ` at ${brief.winner_tco_minor} minor units TCO` : ""}
          </p>
          <table>
            <thead><tr><th>Supplier</th><th>TCO (minor)</th></tr></thead>
            <tbody>
              {brief.ranking.map((r) => (
                <tr key={r.supplier_id}>
                  <td>{r.supplier_id}</td>
                  <td className="mono">{r.tco_minor}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul>
            {brief.cited_lines.map((l, i) => <li key={i}>{l}</li>)}
          </ul>
          <p className="mono">{brief.evidence_note}</p>
          <div className="row">
            <button type="button" onClick={() => void requestApprovals()}>
              Request approvals
            </button>
            <Link href={`/agent/${id}/approval`}>Go to Approval</Link>
          </div>
          {note ? <p role="status">{note}</p> : null}
        </>
      ) : null}
    </Screen>
  );
}
