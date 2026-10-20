// P14 Action Center, wired: dry-run first (forced), execute only on ALLOW,
// idempotent receipts ledger, settle, then the advance to report.
"use client";

import { useEffect, useState, use } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api, stateForError, verdictTone } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Badge, Card, Field, StateBadge } from "@/components/ui";

type External = {
  purchase_orders: { id: string; po_number: string; supplier_id: string; status: string; total_minor: number; at: string }[];
  reservations: { id: string; mission_id: string; status: string; amount_minor: number; currency: string; at: string }[];
  messages: { id: string; subject: string; supplier_id: string; status: string; sent_at: string | null; at: string }[];
};

function hashPayload(payload: string): string {
  // Simple client-side hash of the payload text (F12): the execute
  // idempotency key changes when the payload changes, so a stale ALLOW can
  // never reuse the original receipt for a different payload.
  let h = 0;
  for (let i = 0; i < payload.length; i++) {
    h = (Math.imul(31, h) + payload.charCodeAt(i)) | 0;
  }
  return (h >>> 0).toString(36);
}

export default function ActionsPage(props: { params: Promise<{ id: string }> }) {
  const params = use(props.params);
  const mid = params.id;
  const [actionClass, setActionClass] = useState("AWARD");
  // The payload is never invented here. A material action is refused
  // unless the payload hashes to the approved one, so a placeholder here
  // would only ever produce a NEEDS-APPROVAL verdict and a dead button.
  // It comes from the approval the quorum was granted on.
  const [payload, setPayload] = useState("{}");
  const [tool, setTool] = useState("issue_po_intent");
  const [verdict, setVerdict] = useState("");
  const [policy, setPolicy] = useState("");
  const [receipt, setReceipt] = useState<Record<string, unknown> | null>(null);
  const [replayed, setReplayed] = useState(false);
  const [external, setExternal] = useState<External | null>(null);
  const [note, setNote] = useState("");
  const [denied, setDenied] = useState(false);

  async function loadExternal() {
    // Real objects of record (A3): POs, reservations, outbox messages —
    // what the gated tools actually produced for this mission.
    const [po, br, msg] = await Promise.all([
      api.purchaseOrders(readToken()).catch(() => null),
      api.budgetReservations(readToken()).catch(() => null),
      api.outboxMessages(readToken()).catch(() => null),
    ]);
    const mine = <T extends { mission_id: string }>(rows: T[] | null | undefined): T[] =>
      (rows ?? []).filter((r) => r.mission_id === mid);
    setExternal({
      purchase_orders: mine(po?.purchase_orders),
      reservations: mine(br?.reservations),
      messages: mine(msg?.messages),
    });
  }

  // Pre-fill the action from the approval that was granted, so the hash the
  // server checks is the hash it approved. Loaded once on mount.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const rows = await api.approvalsList(mid, readToken());
        if (cancelled) return;
        const approved = (rows.approvals ?? []).find((a) => a.status === "approved");
        if (!approved) return;
        setActionClass(approved.action_class);
        setPayload(JSON.stringify(approved.payload ?? {}));
      } catch {
        /* no approval yet: the operator picks the action */
      }
    })();
    return () => { cancelled = true; };
  }, [mid]);

  // Stale-gate reset (F11): any change to what is being dry-run clears the
  // verdict, so Execute stays disabled until the NEW payload validates.
  function resetGate() {
    setVerdict("");
    setPolicy("");
    setReceipt(null);
    setReplayed(false);
  }

  async function dryRun() {
    if (denied) return;
    setNote("");
    resetGate();
    try {
      const parsed: unknown = JSON.parse(payload); // guarded (F7)
      const out = await api.dryRun(mid, {
        action_class: actionClass, payload: parsed,
      }, readToken());
      setVerdict(out.verdict);
      setPolicy(String(out.policy));
    } catch (e) {
      setNote(e instanceof Error ? e.message : "dry-run failed");
      setDenied(stateForError(e) === "denied");
    }
  }

  async function execute() {
    if (verdict !== "ALLOW") {
      setNote("Dry-run first — execute stays disabled until ALLOW.");
      return;
    }
    try {
      // Key derives from the payload hash (F12): a changed payload never
      // reuses the original receipt.
      const key = `web-${mid}-${actionClass}-${hashPayload(payload)}`;
      const parsed: unknown = JSON.parse(payload);
      const out = await api.execute(mid, {
        action_class: actionClass, payload: parsed, tool_name: tool,
      }, readToken(), key);
      setReceipt(out.receipt);
      setReplayed(out.replayed);
      setNote(out.replayed ? "Already done — original receipt returned." : "Executed.");
      void loadExternal();
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
    <Screen code="P14" title="Action Center" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Actions" }]}
      primary="Execute" onPrimary={() => void execute()} status="Dry-run first; execute only on ALLOW; receipts are idempotent" state={denied ? "denied" : "success"}>
      <Card>
        <div className="gate-grid">
          <Field label="Action class">
            <select value={actionClass} onChange={(e) => { setActionClass(e.target.value); resetGate(); }}>
              <option>AWARD</option>
              <option>FINANCIAL_COMMIT</option>
              <option>CONTRACTUAL_COMMIT</option>
              <option>EXTERNAL_COMM</option>
            </select>
          </Field>
          <Field label="Tool">
            <select value={tool} onChange={(e) => { setTool(e.target.value); resetGate(); }}>
              <option>issue_po_intent</option>
              <option>reserve_budget_intent</option>
              <option>send_supplier_message</option>
            </select>
          </Field>
          <Field label="Payload (must hash-match the approval)">
            <textarea rows={4} value={payload}
              onChange={(e) => { setPayload(e.target.value); resetGate(); }} />
          </Field>
        </div>
      </Card>
      <div className="row">
        <button type="button" onClick={() => void dryRun()}>Dry-run</button>
        <button type="button" className="primary" disabled={verdict !== "ALLOW"}
          onClick={() => void execute()}>Execute</button>
        <button type="button" onClick={() => void settle()}>Mark actions settled</button>
      </div>
      {verdict ? (
        <p role="status" data-tone={tone} className="row gap-2 text-sm">
          <Badge tone={tone}>{verdict}</Badge>
          <span className="text-text-2">{policy}</span>
        </p>
      ) : null}
      {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
      {receipt ? (
        <pre className="mono">{JSON.stringify({ ...receipt, replayed }, null, 2)}</pre>
      ) : null}
      {external && (external.purchase_orders.length || external.reservations.length || external.messages.length) ? (
        <section>
          <h2 className="mb-3 text-sm font-semibold tracking-tight">Real objects of record</h2>
          <div className="grid gap-2">
            {external.purchase_orders.map((po) => (
              <div key={po.id} className="card row flex-wrap items-center justify-between gap-3 py-3">
                <div className="row gap-3">
                  <StateBadge state="ok" />
                  <span className="mono text-sm font-semibold">{po.po_number}</span>
                  <span className="text-xs text-text-2">{po.supplier_id}</span>
                </div>
                <span className="mono text-sm">{po.total_minor} minor</span>
              </div>
            ))}
            {external.reservations.map((br) => (
              <div key={br.id} className="card row flex-wrap items-center justify-between gap-3 py-3">
                <div className="row gap-3">
                  <StateBadge state="ok" />
                  <span className="text-sm font-semibold">Budget reserved</span>
                </div>
                <span className="mono text-sm">{br.amount_minor} {br.currency}</span>
              </div>
            ))}
            {external.messages.map((m) => (
              <div key={m.id} className="card row flex-wrap items-center justify-between gap-3 py-3">
                <div className="row gap-3">
                  <StateBadge state={m.status === "sent" ? "ok" : "pending"} />
                  <span className="text-sm font-semibold">{m.subject}</span>
                  <span className="text-xs text-text-2">{m.supplier_id}</span>
                </div>
                <Badge tone={m.status === "sent" ? "ok" : "warn"}>{m.status}</Badge>
              </div>
            ))}
          </div>
        </section>
      ) : null}
      <AdvancePanel missionId={mid} toState="report" label="Advance to report" />
    </Screen>
  );
}
