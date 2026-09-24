// Evidence Drawer: every number/claim is one click from its source span.
// Shows quoted text, location, extractor version, confidence, and a
// correction form. Flagged (hostile) spans render with a warning banner.
"use client";

import { useState } from "react";
import type { Span } from "@/lib/api-client";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

export function EvidenceDrawer({
  missionId, span, onClose, onCorrected,
}: {
  missionId: string;
  span: Span | null;
  onClose: () => void;
  onCorrected: (s: Span) => void;
}) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  if (!span) return null;
  async function correct() {
    setBusy(true);
    try {
      const next = await api.correctSpan(missionId, span!.id,
        { field_value: value || span!.field_value, reason: "drawer correction" },
        readToken()) as unknown as Span;
      onCorrected(next);
      onClose();
    } finally {
      setBusy(false);
    }
  }
  return (
    <aside role="dialog" aria-label="Evidence" className="drawer">
      {span.instruction_flag ? (
        <p role="alert" className="warn">
          Quarantined: this span tripped the instruction scan. It is data,
          not instructions, and planners ignore it.
        </p>
      ) : null}
      <h2>{span.field_name}</h2>
      <p className="mono">{span.field_value}</p>
      <blockquote>{span.quoted_text || "(no quoted text)"}</blockquote>
      <dl>
        <dt>Extractor</dt><dd className="mono">{span.extractor_version}</dd>
        <dt>Confidence</dt><dd className="mono">{span.confidence}</dd>
      </dl>
      <label>
        Corrected value
        <input value={value} placeholder={span.field_value}
          onChange={(e) => setValue(e.target.value)} />
      </label>
      <div className="row">
        <button type="button" disabled={busy} onClick={correct}>Apply + flag re-run</button>
        <button type="button" onClick={onClose}>Close</button>
      </div>
    </aside>
  );
}
