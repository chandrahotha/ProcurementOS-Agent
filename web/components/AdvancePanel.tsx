// AdvancePanel: state advance with gate feedback. For approval->action the
// server re-verifies quorum + payload hash, so that step carries the action
// class and exact payload JSON (never trust the client for value math).
// Busy state guards double-submit; JSON.parse is inside the try (F8/F14).
"use client";

import { useState } from "react";
import { api, type Mission } from "@/lib/api-client";
import { readToken } from "@/lib/token";

export function AdvancePanel({
  missionId, toState, label, withPayload = false, onAdvanced,
}: {
  missionId: string;
  toState: string;
  label: string;
  withPayload?: boolean;
  onAdvanced?: (m: Mission) => void;
}) {
  const [cls, setCls] = useState("AWARD");
  const [payload, setPayload] = useState('{"supplier_id": "S-A"}');
  const [note, setNote] = useState("");
  const [missing, setMissing] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  async function go() {
    if (busy) return;
    setNote("");
    setMissing([]);
    const body: Record<string, unknown> = { to_state: toState };
    if (withPayload) {
      try {
        body.action_class = cls;
        // JSON.parse inside the try: malformed JSON surfaces as a validation
        // error, never an unhandled rejection (F8).
        body.payload = JSON.parse(payload);
      } catch {
        setNote("Payload must be valid JSON.");
        return;
      }
    }
    setBusy(true);
    try {
      const m = await api.advance(missionId, body, readToken());
      setNote(`Advanced to ${m.state}.`);
      onAdvanced?.(m);
    } catch (e) {
      const err = e as { message?: string; details?: { missing?: string[] } };
      setNote(err.message ?? "advance refused");
      if (err.details?.missing) setMissing(err.details.missing);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="advance">
      {withPayload ? (
        <>
          <label>Action class
            <select value={cls} onChange={(e) => setCls(e.target.value)}>
              <option>AWARD</option>
              <option>FINANCIAL_COMMIT</option>
              <option>CONTRACTUAL_COMMIT</option>
            </select>
          </label>
          <label>Payload (hash must match the approval)
            <textarea rows={3} value={payload}
              onChange={(e) => setPayload(e.target.value)} />
          </label>
        </>
      ) : null}
      <div className="row">
        <button type="button" className="primary" disabled={busy} onClick={() => void go()}>{label}</button>
      </div>
      {note ? <p role="status">{note}</p> : null}
      {missing.length > 0 ? (
        <p role="alert">Missing evidence for: {missing.join(", ")}</p>
      ) : null}
    </div>
  );
}
