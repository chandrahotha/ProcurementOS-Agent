// AdvancePanel: state advance with gate feedback. For approval->action the
// server re-verifies quorum + payload hash, so that step carries the action
// class and the exact payload JSON (never trust the client for value math).
// Busy state guards double-submit; JSON.parse is inside the try (F8/F14).
"use client";

import { useEffect, useState } from "react";
import { api, type Mission } from "@/lib/api-client";
import { readToken } from "@/lib/token";

export function AdvancePanel({
  missionId, toState, label, withPayload = false, onAdvanced, initialPayload,
}: {
  missionId: string;
  toState: string;
  label: string;
  withPayload?: boolean;
  onAdvanced?: (m: Mission) => void;
  /** The hash-locked payload to carry, when the gate expects one. */
  initialPayload?: string;
}) {
  const [cls, setCls] = useState("AWARD");
  // The payload is never invented here: a material advance is refused unless
  // the payload hashes to the approved one, so a placeholder would only
  // produce an opaque refusal. The caller supplies what was approved.
  const [payload, setPayload] = useState(initialPayload ?? "{}");
  const [note, setNote] = useState("");
  const [missing, setMissing] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (initialPayload != null) setPayload(initialPayload);
  }, [initialPayload]);

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
