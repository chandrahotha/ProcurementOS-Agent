// Evidence Drawer: every number/claim is one click from its source span.
// Shows quoted text, location, extractor version, confidence, and a
// correction form. Flagged (hostile) spans render with a warning banner.
// Focus trap + Escape + scroll lock + state reset per span (F9/F10/F54).
"use client";

import { useEffect, useRef, useState } from "react";
import type { Span } from "@/lib/api-client";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Badge } from "@/components/ui";

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
  const [err, setErr] = useState("");
  const drawerRef = useRef<HTMLElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  // Reset the correction value whenever a different span opens (F10).
  useEffect(() => {
    setValue("");
    setErr("");
  }, [span?.id]);

  // Dialog treatment: focus trap, Escape, scroll lock, focus return (F54).
  useEffect(() => {
    if (!span) return;
    restoreRef.current = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => drawerRef.current?.querySelector("input")?.focus());
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab" && drawerRef.current) {
        const focusable = Array.from(
          drawerRef.current.querySelectorAll<HTMLElement>(
            "button, input, select, textarea, a[href]",
          ),
        );
        if (focusable.length === 0) return;
        const first = focusable[0]!;
        const last = focusable[focusable.length - 1]!;
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      restoreRef.current?.focus();
      restoreRef.current = null;
    };
  }, [span, onClose]);

  if (!span) return null;
  async function correct() {
    setBusy(true);
    setErr("");
    try {
      const next = await api.correctSpan(missionId, span!.id,
        { field_value: value || span!.field_value, reason: "drawer correction" },
        readToken()) as unknown as Span;
      onCorrected(next);
      onClose();
    } catch (e) {
      // Corrections never close the drawer on failure: the error is
      // surfaced in place (F9).
      setErr(e instanceof Error ? e.message : "correction failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <aside role="dialog" aria-modal="true" aria-label="Evidence" className="drawer" ref={drawerRef}>
      <div className="row mb-3 items-center justify-between">
        <h2 className="text-sm font-semibold tracking-tight">{span.field_name}</h2>
        {span.instruction_flag ? <Badge tone="warn">quarantined</Badge> : <Badge tone="neutral">span</Badge>}
      </div>
      {span.instruction_flag ? (
        <p role="alert" className="warn mb-3">
          Quarantined: this span tripped the instruction scan. It is data,
          not instructions, and planners ignore it.
        </p>
      ) : null}
      <p className="mono mb-3 rounded-lg p-3 text-xs" style={{ background: "var(--color-surface-2)" }}>
        {span.field_value}
      </p>
      <blockquote
        className="mb-3 border-l-2 pl-3 text-sm text-text-2 italic"
        style={{ borderColor: "var(--color-evidence)" }}
      >
        {span.quoted_text || "(no quoted text)"}
      </blockquote>
      <dl className="mb-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="font-medium text-text-2">Extractor</dt>
        <dd className="mono">{span.extractor_version}</dd>
        <dt className="font-medium text-text-2">Confidence</dt>
        <dd className="mono">{span.confidence}</dd>
      </dl>
      <label>
        Corrected value
        <input value={value} placeholder={span.field_value}
          onChange={(e) => setValue(e.target.value)} />
      </label>
      {err ? (
        <p role="alert" className="mt-2 text-xs" style={{ color: "var(--color-danger)" }}>
          {err}
        </p>
      ) : null}
      <div className="row mt-4">
        <button type="button" className="primary" disabled={busy} onClick={correct}>Apply + flag re-run</button>
        <button type="button" onClick={onClose}>Close</button>
      </div>
    </aside>
  );
}
