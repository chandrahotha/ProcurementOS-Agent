// P13 Human Approval, wired + mobile-first: request per the policy matrix,
// lane queue with quorum progress, big Approve/Reject (reason mandatory
// on reject). Non-lane members get the read-only denied state from the API.
"use client";

import { useState } from "react";
import { Screen } from "@/components/Screen";
import { ApiError, api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Row = { id: string; lane: string; status: string };

export default function ApprovalPage({ params }: { params: { id: string } }) {
  const mid = params.id;
  const [rows, setRows] = useState<Row[]>([]);
  const [quorum, setQuorum] = useState<boolean | null>(null);
  const [actionClass, setActionClass] = useState("AWARD");
  const [payload, setPayload] = useState(
    '{"supplier_id": "S-A", "value_minor": 6000000, "threshold_minor": 5000000}');
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [denied, setDenied] = useState(false);

  async function request() {
    setNote("");
    try {
      const out = await api.requestApprovals(mid, {
        action_class: actionClass,
        payload: JSON.parse(payload),
        value_minor: JSON.parse(payload).value_minor ?? 0,
      }, readToken());
      setRows(out.approvals);
      setQuorum(false);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "request failed");
    }
  }

  async function decide(aid: string, decision: "approved" | "rejected") {
    if (decision === "rejected" && !reason.trim()) {
      setNote("Reject needs a reason — it goes into the audit trail.");
      return;
    }
    try {
      const out = await api.decide(mid, aid, { decision, reason }, readToken());
      setRows((cur) => cur.map((a) => (a.id === aid ? { ...a, status: out.status } : a)));
      setQuorum(out.quorum_met);
      setNote(`Recorded: ${out.status}. Quorum ${out.quorum_met ? "met" : "not yet met"}.`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setDenied(true);
      setNote(e instanceof Error ? e.message : "decide failed");
    }
  }

  return (
    <Screen code="P13" title="Human Approval" breadcrumb="Mission / Approval"
      primary="Approve" state={denied ? "denied" : "success"}>
      <div className="gate-grid">
        <label>Action class
          <select value={actionClass} onChange={(e) => setActionClass(e.target.value)}>
            <option>AWARD</option>
            <option>FINANCIAL_COMMIT</option>
            <option>CONTRACTUAL_COMMIT</option>
            <option>EXTERNAL_COMM</option>
            <option>POLICY_OVERRIDE</option>
          </select>
        </label>
        <label>Payload (exact JSON that will be hash-locked)
          <textarea rows={4} value={payload} onChange={(e) => setPayload(e.target.value)} />
        </label>
        <button type="button" onClick={() => void request()}>Request approvals</button>
      </div>
      {quorum !== null ? (
        <p role="status">Quorum {quorum ? "met — the action may proceed." : "pending."}</p>
      ) : null}
      {note ? <p role="status">{note}</p> : null}
      <label>Reason (required to reject)
        <input value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder="Why this decision" />
      </label>
      <ul className="approval-list">
        {rows.map((a) => (
          <li key={a.id} className="approval-card">
            <strong>{a.lane}</strong> <span>{a.status}</span>
            <span className="mono">{a.id.slice(0, 8)}</span>
            <div className="row">
              <button type="button" className="big"
                onClick={() => void decide(a.id, "approved")}>Approve</button>
              <button type="button" className="big danger"
                onClick={() => void decide(a.id, "rejected")}>Reject</button>
            </div>
          </li>
        ))}
      </ul>
    </Screen>
  );
}
