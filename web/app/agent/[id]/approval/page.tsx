// P13 Human Approval, wired: loads the real approval queue for the mission,
// decides per lane, and carries the hash-locked payload through to action.
// Busy state guards double-submit; decisions are terminal (server-enforced).
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, Field, StateBadge } from "@/components/ui";

type Row = { id: string; lane: string; status: string; action_class: string;
  expires_at: string | null; payload_hash: string; payload: Record<string, unknown> };

/** The approval rows for a mission. Module level so the effect and the
 *  reload-after-decision path share one implementation. */
async function fetchApprovals(id: string): Promise<Row[]> {
  const d = await api.approvalsList(id, readToken());
  return (d.approvals ?? []).map((a) => ({ ...a, payload: a.payload ?? {} }));
}

export default function ApprovalPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [rows, setRows] = useState<Row[]>([]);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [denied, setDenied] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const list = await fetchApprovals(id);
      setRows(list);
      if (list.length === 0) setNote("No approvals yet — request them from the Decision Brief.");
    } catch { setDenied(true); }
  }

  // The fetch lives inside the effect so the effect has no dependency it
  // cannot satisfy, and so a response that arrives after the screen has
  // moved on cannot overwrite the newer screen's data (F16).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await fetchApprovals(id);
        if (cancelled) return;
        setRows(list);
        if (list.length === 0) setNote("No approvals yet — request them from the Decision Brief.");
      } catch { if (!cancelled) setDenied(true); }
    })();
    return () => { cancelled = true; };
  }, [id]);

  async function decide(aid: string, decision: "approved" | "rejected") {
    if (busy) return;
    if (decision === "rejected" && !reason.trim()) {
      setNote("Reject needs a reason — it goes into the audit trail.");
      return;
    }
    setNote("");
    setBusy(true);
    try {
      const out = await api.decide(id, aid, { decision, reason }, readToken());
      setNote(`Recorded: ${out.status}. Quorum ${out.quorum_met ? "met" : "not yet met"}.`);
      await load();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "decide failed");
    } finally {
      setBusy(false);
    }
  }

  const pending = rows.filter((r) => r.status === "pending");
  const approved = rows.filter((r) => r.status === "approved");
  const quorum = rows.length > 0 && pending.length === 0 && approved.length > 0;
  // The action advance is hash-locked: it must carry the payload that was
  // approved, byte for byte. It comes from the approval row, not from a
  // value the operator retypes.
  const approvedPayload = approved.length
    ? JSON.stringify(approved[0]?.payload ?? {})
    : undefined;

  return (
    <Screen code="P13" title="Human Approval" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Approval" }]}
      primary="Approve" onPrimary={() => pending[0] && void decide(pending[0].id, "approved")}
      status="Lane decisions are terminal and hash-locked"
      state={denied ? "denied" : "success"}>
      {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
      <Field label="Reason (required to reject)">
        <input value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder="Why this decision" />
      </Field>
      {rows.length === 0 ? (
        <EmptyState icon="shield" title="No approvals yet"
          body="Request them from the Decision Brief — the server picks the lanes per the policy matrix."
          action={{ label: "Go to Decision Brief", href: `/agent/${id}/decision` }} />
      ) : (
        <ul className="approval-list">
          {rows.map((a) => (
            <li key={a.id} className="approval-card">
              <div className="row flex-wrap items-center justify-between gap-2">
                <div className="row gap-2">
                  <strong className="text-sm">{a.lane}</strong>
                  <StateBadge state={a.action_class} />
                  <StateBadge state={a.status} />
                </div>
                <span className="mono text-xs text-text-2" title={a.payload_hash}>
                  hash {a.payload_hash}…
                </span>
              </div>
              {a.status === "pending" ? (
                <div className="row">
                  <button type="button" className="primary big flex-1"
                    disabled={busy}
                    onClick={() => void decide(a.id, "approved")}>Approve</button>
                  <button type="button" className="danger big flex-1"
                    disabled={busy}
                    onClick={() => void decide(a.id, "rejected")}>Reject</button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {quorum ? (
        <AdvancePanel missionId={id} toState="action"
          label="Advance to action (quorum verified)" withPayload
          initialPayload={approvedPayload} />
      ) : (
        <p className="text-xs text-text-2">Advance to action unlocks when every lane has approved and the
          payload hash still matches.</p>
      )}
    </Screen>
  );
}
