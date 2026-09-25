// P14 Action Center, wired: dry-run first (forced), execute only on ALLOW,
// idempotent receipts ledger, settle, then the advance to report.
"use client";

import { useState, use } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api, verdictTone } from "@/lib/api-client";
import { readToken } from "@/lib/token";

export default function ActionsPage(props: { params: Promise<{ id: string }> }) {
  const params = use(props.params);
  const mid = params.id;
  const [actionClass, setActionClass] = useState("AWARD");
  const [payload, setPayload] = useState(
    '{"supplier_id": "S-A", "value_minor": 6000000, "threshold_minor": 5000000}');
  const [tool, setTool] = useState("issue_po_intent");
  const [verdict, setVerdict] = useState("");
  const [policy, setPolicy] = useState("");
  const [receipt, setReceipt] = useState<Record<string, unknown> | null>(null);
  const [replayed, setReplayed] = useState(false);
  const [note, setNote] = useState("");

  async function dryRun() {
    setNote("");
    setReceipt(null);
    const out = await api.dryRun(mid, {
      action_class: actionClass, payload: JSON.parse(payload),
    }, readToken());
    setVerdict(out.verdict);
    setPolicy(String(out.policy));
  }

  async function execute() {
    if (verdict !== "ALLOW") {
      setNote("Dry-run first — execute stays disabled until ALLOW.");
      return;
    }
    try {
      const key = `web-${mid}-${actionClass}-v1`;
      const out = await api.execute(mid, {
        action_class: actionClass, payload: JSON.parse(payload), tool_name: tool,
      }, readToken(), key);
      setReceipt(out.receipt);
      setReplayed(out.replayed);
      setNote(out.replayed ? "Already done — original receipt returned." : "Executed.");
    } catch (e) {
      setNote(e instanceof Error ? e.message : "execute failed");
    }
  }

  async function settle() {
    setNote("");
    try {
      await api.settle(mid, readToken());
      setNote("Actions marked settled (executed or explicitly skipped).");
    } catch (e) {
      setNote(e instanceof Error ? e.message : "settle failed");
    }
  }

  const tone = verdictTone(verdict || "DENY");
  return (
    <Screen code="P14" title="Action Center" breadcrumb="Mission / Actions"
      primary="Execute" state="success">
      <label>Action class
        <select value={actionClass} onChange={(e) => setActionClass(e.target.value)}>
          <option>AWARD</option>
          <option>FINANCIAL_COMMIT</option>
          <option>CONTRACTUAL_COMMIT</option>
          <option>EXTERNAL_COMM</option>
        </select>
      </label>
      <label>Tool
        <select value={tool} onChange={(e) => setTool(e.target.value)}>
          <option>issue_po_intent</option>
          <option>reserve_budget_intent</option>
          <option>send_supplier_message</option>
        </select>
      </label>
      <label>Payload (must hash-match the approval)
        <textarea rows={4} value={payload} onChange={(e) => setPayload(e.target.value)} />
      </label>
      <div className="row">
        <button type="button" onClick={() => void dryRun()}>Dry-run</button>
        <button type="button" disabled={verdict !== "ALLOW"}
          onClick={() => void execute()}>Execute</button>
        <button type="button" onClick={() => void settle()}>Mark actions settled</button>
      </div>
      {verdict ? (
        <p role="status" data-tone={tone}>
          {verdict} — {policy}
        </p>
      ) : null}
      {note ? <p role="status">{note}</p> : null}
      {receipt ? (
        <pre className="mono">{JSON.stringify({ ...receipt, replayed }, null, 2)}</pre>
      ) : null}
      <AdvancePanel missionId={mid} toState="report" label="Advance to report" />
    </Screen>
  );
}
