// P13 Human Approval, wired: loads the real approval queue for the mission,
// decides per lane, and carries the hash-locked payload through to action.
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Row = { id: string; lane: string; status: string; action_class: string;
  expires_at: string | null; payload_hash: string };

export default function ApprovalPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [rows, setRows] = useState<Row[]>([]);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [denied, setDenied] = useState(false);

  async function load() {
    try {
      const d = await api.approvalsList(id, readToken());
      setRows(d.approvals);
      if (d.approvals.length === 0) setNote("No approvals yet — request them from the Decision Brief.");
    } catch { setDenied(true); }
  }

  useEffect(() => { void load(); /* eslint-disable-next-line */ }, [id]);

  async function decide(aid: string, decision: "approved" | "rejected") {
    if (decision === "rejected" && !reason.trim()) {
      setNote("Reject needs a reason — it goes into the audit trail.");
      return;
    }
    setNote("");
    try {
      const out = await api.decide(id, aid, { decision, reason }, readToken());
      setNote(`Recorded: ${out.status}. Quorum ${out.quorum_met ? "met" : "not yet met"}.`);
      await load();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "decide failed");
    }
  }

  const pending = rows.filter((r) => r.status === "pending");
  const approved = rows.filter((r) => r.status === "approved");
  const quorum = rows.length > 0 && pending.length === 0 && approved.length > 0;

  return (
    <Screen code="P13" title="Human Approval" breadcrumb="Mission / Approval"
      primary="Approve" state={denied ? "denied" : "success"}>
      {note ? <p role="status">{note}</p> : null}
      <label>Reason (required to reject)
        <input value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder="Why this decision" />
      </label>
      <ul className="approval-list">
        {rows.map((a) => (
          <li key={a.id} className="approval-card">
            <strong>{a.lane}</strong> <span>{a.action_class}</span>
            <span>{a.status}</span>
            <span className="mono">hash {a.payload_hash}…</span>
            {a.status === "pending" ? (
              <div className="row">
                <button type="button" className="big"
                  onClick={() => void decide(a.id, "approved")}>Approve</button>
                <button type="button" className="big danger"
                  onClick={() => void decide(a.id, "rejected")}>Reject</button>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
      {quorum ? (
        <AdvancePanel missionId={id} toState="action"
          label="Advance to action (quorum verified)" withPayload />
      ) : (
        <p>Advance to action unlocks when every lane has approved and the
          payload hash still matches.</p>
      )}
    </Screen>
  );
}
