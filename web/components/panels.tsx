// The panels the brain names and the repo never built: ActivityLog, Timeline,
// DiffViewer, RuleExplanation, DryRunCard, BriefCard, ConfirmDialog,
// ExportButton, AIAssistantPanel, UploadZone, ApprovalPanel, AutonomyDial,
// StateRail.
//
// The rule every one of them obeys: the screen shows what the server
// decided and never decides anything itself. The AI panel in particular
// labels an AI note as an AI note and shows its citation state, because a
// claim without a citation is not evidence and must not read like it.
"use client";

import React, { useEffect, useRef, useState } from "react";
import { Badge, Card, type Tone } from "@/components/ui";
import { Icon, type IconName } from "@/components/icons";
import { ConfidenceBadge, CoverageRing, Money } from "@/components/data";

// --------------------------------------------------------------- StateRail

export const MISSION_STATES = [
  "intake",
  "plan",
  "evidence",
  "analysis",
  "scenarios",
  "negotiation",
  "approval",
  "action",
  "report",
] as const;

export function StateRail({
  current,
  coverage,
  dial,
  onBriefMe,
}: {
  current: string;
  coverage?: number;
  dial?: string;
  onBriefMe?: () => void;
}) {
  const idx = MISSION_STATES.indexOf(current as (typeof MISSION_STATES)[number]);
  return (
    <div className="card grid gap-3">
      <div className="row justify-between">
        <ol className="row flex-nowrap gap-1 overflow-x-auto" aria-label="Mission progress">
          {MISSION_STATES.map((s, i) => {
            const done = idx > i;
            const here = idx === i;
            return (
              <li key={s} className="flex min-w-0 flex-col items-center gap-1">
                <span
                  aria-current={here ? "step" : undefined}
                  className="flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-semibold"
                  style={{
                    background: done
                      ? "var(--color-ok)"
                      : here
                        ? "var(--color-accent)"
                        : "var(--color-surface-2)",
                    color: done || here ? "#fff" : "var(--color-text-2)",
                  }}
                >
                  {done ? <Icon name="check" size={12} /> : i + 1}
                </span>
                <span
                  className="text-[10px] whitespace-nowrap"
                  style={{ color: here ? "var(--color-text)" : "var(--color-text-2)" }}
                >
                  {s}
                </span>
              </li>
            );
          })}
        </ol>
        {coverage != null ? <CoverageRing pct={coverage} /> : null}
      </div>
      <div className="row justify-between text-xs text-text-2">
        <span className="row gap-2">
          {dial ? (
            <Badge tone={dial === "GUARDED" ? "warn" : dial === "ASSISTED" ? "info" : "neutral"}>
              {dial}
            </Badge>
          ) : null}
          <span>step {Math.max(1, idx + 1)} of {MISSION_STATES.length}</span>
        </span>
        {onBriefMe ? (
          <button type="button" className="primary" onClick={onBriefMe}>
            Brief me
          </button>
        ) : null}
      </div>
    </div>
  );
}

// -------------------------------------------------------------- ActivityLog

export type ActivityEvent = {
  kind: string;
  at?: string;
  actor?: string | null;
  payload?: Record<string, unknown>;
  tool?: string;
  status?: string;
};

export function ActivityLog({
  events,
  title = "Activity",
  live = false,
  empty = "No activity yet.",
}: {
  events: ActivityEvent[];
  title?: string;
  live?: boolean;
  empty?: string;
}) {
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!paused && live) endRef.current?.scrollIntoView({ block: "nearest" });
  }, [events.length, paused, live]);

  const kinds = Array.from(new Set(events.map((e) => e.kind)));
  const shown = filter
    ? events.filter((e) => e.kind.includes(filter) || e.kind.includes("."))
    : events;

  return (
    <Card className="grid gap-2">
      <div className="row justify-between">
        <h2 className="card-title row gap-2">
          <Icon name="activity" size={14} />
          {title}
        </h2>
        {live ? (
          <div className="row gap-2">
            <label className="flex-row items-center gap-1.5 text-[11px]">
              <span className="sr-only">Filter activity by kind</span>
              <select value={filter} onChange={(e) => setFilter(e.target.value)}>
                <option value="">all</option>
                {kinds.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="ghost px-2 py-1 text-xs" onClick={() => setPaused((p) => !p)}>
              {paused ? "Resume" : "Pause"}
            </button>
          </div>
        ) : null}
      </div>
      {shown.length === 0 ? (
        <p className="text-sm text-text-2">{empty}</p>
      ) : (
        <ol className="grid list-none gap-1 p-0" aria-live={live && !paused ? "polite" : "off"}>
          {shown.map((e, i) => (
            <li key={`${e.kind}-${i}`} className="row gap-2 border-b border-border py-1 text-xs last:border-0">
              <span className="mono shrink-0 text-text-2">{e.at ?? ""}</span>
              <span className="font-medium">{e.kind}</span>
              {e.tool ? <Badge tone="info">{e.tool}</Badge> : null}
              {e.status ? <Badge tone={e.status === "ok" ? "ok" : "warn"}>{e.status}</Badge> : null}
              {e.actor ? <span className="text-text-2">{e.actor}</span> : null}
            </li>
          ))}
          <div ref={endRef} />
        </ol>
      )}
    </Card>
  );
}

// ----------------------------------------------------------------- Timeline

export function Timeline({
  events,
  caption = "Mission timeline",
}: {
  events: { kind: string; at?: string; actor?: string | null }[];
  caption?: string;
}) {
  if (events.length === 0) {
    return <p className="text-sm text-text-2">Nothing recorded yet.</p>;
  }
  return (
    <ol className="grid list-none gap-0 p-0" aria-label={caption}>
      {events.map((e, i) => (
        <li key={`${e.kind}-${i}`} className="row gap-3 border-l-2 border-border py-1.5 pl-4">
          <span
            aria-hidden="true"
            className="-ml-[21px] mt-1.5 h-2 w-2 rounded-full"
            style={{ background: "var(--color-accent)" }}
          />
          <span className="min-w-0">
            <span className="text-sm font-medium">{e.kind}</span>
            <span className="mono ml-2 text-[11px] text-text-2">{e.at ?? ""}</span>
            {e.actor ? <span className="ml-2 text-[11px] text-text-2">{e.actor}</span> : null}
          </span>
        </li>
      ))}
    </ol>
  );
}

// --------------------------------------------------------------- DiffViewer

export function DiffViewer({
  left,
  right,
  leftLabel = "before",
  rightLabel = "after",
}: {
  left: Record<string, unknown>;
  right: Record<string, unknown>;
  leftLabel?: string;
  rightLabel?: string;
}) {
  const keys = Array.from(new Set([...Object.keys(left ?? {}), ...Object.keys(right ?? {})])).sort();
  const changed = keys.filter((k) => JSON.stringify(left?.[k]) !== JSON.stringify(right?.[k]));
  if (changed.length === 0) {
    return <p className="text-sm text-text-2">No differences.</p>;
  }
  return (
    <div className="table-card">
      <table>
        <caption className="sr-only">
          Differences between {leftLabel} and {rightLabel}
        </caption>
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">{leftLabel}</th>
            <th scope="col">{rightLabel}</th>
          </tr>
        </thead>
        <tbody>
          {changed.map((k) => (
            <tr key={k}>
              <td data-label="Field" className="font-medium">
                {k}
              </td>
              <td data-label={leftLabel} className="mono text-text-2">
                {String(left?.[k] ?? "—")}
              </td>
              <td data-label={rightLabel} className="mono font-semibold">
                {String(right?.[k] ?? "—")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --------------------------------------------------------- RuleExplanation

export function RuleExplanation({
  version,
  weights,
  tolerances,
  effectiveFrom,
  changelog,
}: {
  version: string;
  weights?: Record<string, unknown>;
  tolerances?: Record<string, unknown>;
  effectiveFrom?: string;
  changelog?: string;
}) {
  return (
    <Card className="grid gap-2 text-sm">
      <div className="row justify-between">
        <span className="row gap-2">
          <Icon name="sliders" size={14} />
          <strong>Rule {version}</strong>
        </span>
        {effectiveFrom ? <span className="mono text-xs text-text-2">from {effectiveFrom}</span> : null}
      </div>
      {weights && Object.keys(weights).length ? (
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-text-2">Weights</div>
          <ul className="mono list-none gap-1 p-0 text-xs">
            {Object.entries(weights).map(([k, v]) => (
              <li key={k} className="row justify-between">
                <span>{k}</span>
                <span>{String(v)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {tolerances && Object.keys(tolerances).length ? (
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-text-2">Tolerances</div>
          <ul className="mono list-none gap-1 p-0 text-xs">
            {Object.entries(tolerances).map(([k, v]) => (
              <li key={k} className="row justify-between">
                <span>{k}</span>
                <span>{String(v)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {changelog ? <p className="text-xs text-text-2">{changelog}</p> : null}
    </Card>
  );
}

// ---------------------------------------------------------------- DryRunCard

export function DryRunCard({
  verdict,
  policy,
  payload,
  actionClass,
  valueMinor,
  currency = "INR",
}: {
  verdict: string;
  policy?: string;
  payload?: unknown;
  actionClass?: string;
  valueMinor?: number;
  currency?: string;
}) {
  const tone: Tone =
    verdict === "ALLOW" ? "ok" : verdict === "DENY" ? "bad" : "warn";
  return (
    <Card className="grid gap-2">
      <div className="row justify-between">
        <span className="row gap-2 text-sm font-semibold">
          <Icon name="shield" size={14} />
          {actionClass ?? "action"}
        </span>
        <Badge tone={tone}>{verdict}</Badge>
      </div>
      {policy ? <p className="text-xs text-text-2">{policy}</p> : null}
      {valueMinor != null ? (
        <p className="text-sm">
          Value impact: <Money minor={valueMinor} currency={currency} />
        </p>
      ) : null}
      {payload != null ? (
        <pre className="mono">{JSON.stringify(payload, null, 2)}</pre>
      ) : null}
    </Card>
  );
}

// ---------------------------------------------------------------- BriefCard

export type BriefOut = {
  winner_supplier_id: string | null;
  winner_tco_minor: number | null;
  ranking: { supplier_id: string; tco_minor: number }[];
  candidate_scenarios: string[];
  exceptions: { stale_fx_suppliers: string[]; lines_ranked: number };
  evidence_note: string;
  cited_lines: string[];
  ai?: { ran: boolean; status: string; verdict: string; cited: boolean };
  ai_draft?: { text: string; cited: boolean; verdict: string; note: string };
};

export function BriefCard({
  brief,
  currency = "INR",
  onRequestApprovals,
}: {
  brief: BriefOut;
  currency?: string;
  onRequestApprovals?: () => void;
}) {
  return (
    <Card className="grid gap-4">
      <div className="row justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-text-2">
            Recommendation
          </div>
          <div className="mt-1 row items-baseline gap-2">
            <strong className="text-xl">{brief.winner_supplier_id ?? "—"}</strong>
            {brief.winner_tco_minor != null ? (
              <span className="mono text-sm text-text-2">
                at <Money minor={brief.winner_tco_minor} currency={currency} /> TCO
              </span>
            ) : null}
          </div>
        </div>
        {onRequestApprovals ? (
          <button type="button" className="primary" onClick={onRequestApprovals}>
            Request approvals
          </button>
        ) : null}
      </div>

      {brief.exceptions.stale_fx_suppliers.length ? (
        <p className="warn row gap-2 text-xs">
          <Icon name="alert" size={14} />
          Stale FX for {brief.exceptions.stale_fx_suppliers.join(", ")} — the ranking
          treats those rows as expired.
        </p>
      ) : null}

      <div>
        <h3 className="mb-2 text-sm font-semibold">Evidence</h3>
        <ul className="grid list-none gap-1 p-0 text-sm">
          {brief.cited_lines.map((l, i) => (
            <li key={`${l}-${i}`} className="row gap-2">
              <Icon name="link" size={13} />
              <span>{l}</span>
            </li>
          ))}
        </ul>
        <p className="mono mt-2 text-xs text-text-2">{brief.evidence_note}</p>
      </div>

      {brief.ai_draft ? (
        <div className="grid gap-1 rounded-lg p-3" style={{ background: "var(--color-warn-soft)" }}>
          <div className="row gap-2 text-xs font-semibold" style={{ color: "var(--color-warn)" }}>
            <Icon name="sparkles" size={13} />
            AI analysis — uncited
            <Badge tone="warn">{brief.ai_draft.verdict}</Badge>
          </div>
          <p className="text-sm">{brief.ai_draft.text}</p>
          <p className="text-[11px] opacity-80">{brief.ai_draft.note}</p>
        </div>
      ) : null}
    </Card>
  );
}

// ------------------------------------------------------------ ConfirmDialog

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  tone = "primary",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: React.ReactNode;
  confirmLabel?: string;
  tone?: "primary" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (open) ref.current?.focus();
  }, [open]);
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgb(15 23 42 / 0.45)" }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <Card className="grid max-w-md gap-3">
        <h2 className="card-title">{title}</h2>
        <div className="text-sm text-text-2">{body}</div>
        <div className="row justify-end gap-2">
          <button type="button" className="ghost" onClick={onCancel}>
            Cancel
          </button>
          <button
            ref={ref}
            type="button"
            className={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </Card>
    </div>
  );
}

// ------------------------------------------------------------- ExportButton

export function ExportButton({
  formats = ["CSV", "XLSX", "PDF"],
  onExport,
  busy,
}: {
  formats?: string[];
  onExport: (format: string) => void;
  busy?: boolean;
}) {
  return (
    <div className="row gap-2">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-text-2">Export</span>
      {formats.map((f) => (
        <button
          key={f}
          type="button"
          disabled={busy}
          onClick={() => onExport(f)}
          title={`Export as ${f}`}
        >
          <span className="row gap-1">
            <Icon name="download" size={13} />
            {f}
          </span>
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------- AIAssistantPanel

export function AIAssistantPanel({
  ran,
  status,
  verdict,
  cited,
  text,
  note,
  children,
}: {
  ran: boolean;
  status: string;
  verdict?: string;
  cited?: boolean;
  text?: string;
  note?: string;
  children?: React.ReactNode;
}) {
  if (!ran) {
    return (
      <Card className="grid gap-2">
        <h3 className="card-title row gap-2">
          <Icon name="sparkles" size={14} />
          AI
        </h3>
        <p className="text-sm text-text-2">
          No AI provider is configured. The deterministic results on this screen are
          unaffected — the math never depended on a model.
        </p>
      </Card>
    );
  }
  const degraded = status.startsWith("degraded");
  const isCited = cited === true;
  return (
    <Card className="grid gap-2">
      <h3 className="card-title row gap-2">
        <Icon name="sparkles" size={14} />
        AI
        {degraded ? (
          <Badge tone="warn">AI unavailable — deterministic math unaffected</Badge>
        ) : isCited ? (
          <Badge tone="ok">cited</Badge>
        ) : (
          <Badge tone="warn">uncited</Badge>
        )}
      </h3>
      {text ? <p className="text-sm">{text}</p> : null}
      {note ? <p className="text-xs text-text-2">{note}</p> : null}
      {verdict ? <p className="mono text-[11px] text-text-2">scan: {verdict}</p> : null}
      {children}
    </Card>
  );
}

// ---------------------------------------------------------------- UploadZone

export function UploadZone({
  onFiles,
  accept = ".pdf,.xlsx,.docx,.csv",
  disabled,
  hint = "Drop a quote or contract, or choose a file. Everything is scanned before it is read.",
}: {
  onFiles: (files: File[]) => void;
  accept?: string;
  disabled?: boolean;
  hint?: string;
}) {
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  return (
    <div
      className="card flex flex-col items-center gap-3 rounded-xl border-2 border-dashed p-6 text-center"
      style={{
        borderColor: over ? "var(--color-accent)" : "var(--color-border)",
        background: over ? "var(--color-accent-soft)" : undefined,
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (disabled) return;
        const files = Array.from(e.dataTransfer.files);
        if (files.length) onFiles(files);
      }}
    >
      <span style={{ color: "var(--color-accent)" }}>
        <Icon name="upload" size={22} />
      </span>
      <label className="text-center">
        <span className="text-sm font-semibold">Upload a document</span>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          disabled={disabled}
          className="mt-2"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) onFiles(files);
            e.target.value = "";
          }}
        />
      </label>
      <p className="max-w-sm text-xs text-text-2">{hint}</p>
    </div>
  );
}

// ------------------------------------------------------------- ApprovalPanel

export type ApprovalRow = {
  id: string;
  lane: string;
  status: string;
  action_class: string;
  expires_at: string | null;
  payload_hash: string;
};

export function ApprovalPanel({
  approvals,
  onDecide,
  busy,
  canDecide = false,
}: {
  approvals: ApprovalRow[];
  onDecide?: (id: string, decision: "approved" | "rejected", reason: string) => void;
  busy?: boolean;
  canDecide?: boolean;
}) {
  const [reason, setReason] = useState("");
  const byLane = new Map<string, ApprovalRow[]>();
  for (const a of approvals) {
    byLane.set(a.lane, [...(byLane.get(a.lane) ?? []), a]);
  }
  if (approvals.length === 0) {
    return <p className="text-sm text-text-2">No approvals yet — request them from the Decision Brief.</p>;
  }
  const lanes = Array.from(byLane.keys()).sort();
  return (
    <div className="grid gap-4">
      {lanes.map((lane) => (
        <section key={lane} className="grid gap-2">
          <div className="row justify-between">
            <h3 className="card-title row gap-2 capitalize">
              <Icon name="shield" size={14} />
              {lane} lane
            </h3>
            <span className="text-xs text-text-2">
              {byLane.get(lane)!.filter((a) => a.status === "approved").length}/
              {byLane.get(lane)!.length} approved
            </span>
          </div>
          <ul className="approval-list">
            {byLane.get(lane)!.map((a) => (
              <li key={a.id} className="approval-card">
                <div className="row flex-wrap items-center justify-between gap-2">
                  <span className="row gap-2">
                    <strong className="text-sm">{a.action_class}</strong>
                    <Badge tone={a.status === "approved" ? "ok" : a.status === "rejected" ? "bad" : "warn"}>
                      {a.status}
                    </Badge>
                  </span>
                  {a.expires_at ? (
                    <span className="mono text-[11px] text-text-2">expires {a.expires_at}</span>
                  ) : null}
                </div>
                <span className="mono truncate text-[11px] text-text-2" title={a.payload_hash}>
                  payload hash {a.payload_hash}…
                </span>
                {a.status === "pending" && canDecide && onDecide ? (
                  <div className="row gap-2">
                    <button
                      type="button"
                      className="primary big flex-1"
                      disabled={busy}
                      onClick={() => onDecide(a.id, "approved", reason || "approved")}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="danger big flex-1"
                      disabled={busy}
                      onClick={() => onDecide(a.id, "rejected", reason || "rejected")}
                    >
                      Reject
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
      {canDecide ? (
        <label className="max-w-md">
          Reason (required to reject)
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why this decision"
          />
        </label>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------- AutonomyDial

export function AutonomyDial({
  level,
  onChange,
  canChange = false,
}: {
  level: string;
  onChange?: (level: string) => void;
  canChange?: boolean;
}) {
  const order = ["ASSISTED", "SUPERVISED", "GUARDED"];
  const desc: Record<string, string> = {
    ASSISTED: "every tool call needs human confirm",
    SUPERVISED: "auto tools run, material gated",
    GUARDED: "within caps, tighter tolerances",
  };
  return (
    <div className="card grid gap-2">
      <div className="row justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-text-2">
          Autonomy dial
        </span>
        <Badge tone={level === "GUARDED" ? "warn" : level === "ASSISTED" ? "info" : "neutral"}>
          {level}
        </Badge>
      </div>
      {canChange && onChange ? (
        <div className="row gap-1" role="radiogroup" aria-label="Autonomy dial">
          {order.map((l) => (
            <button
              key={l}
              type="button"
              role="radio"
              aria-checked={level === l}
              className={level === l ? "primary" : "ghost"}
              onClick={() => onChange(l)}
              title={desc[l]}
            >
              {l}
            </button>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-2">{desc[level] ?? ""}</p>
      )}
    </div>
  );
}

// --------------------------------------------------------------- Exceptions

export function ExceptionList({
  items,
}: {
  items: { label: string; detail?: string; tone?: Tone; icon?: IconName }[];
}) {
  if (items.length === 0) return null;
  return (
    <ul className="grid list-none gap-1 p-0">
      {items.map((i, idx) => (
        <li
          key={`${i.label}-${idx}`}
          className="row gap-2 rounded-lg p-2 text-sm"
          style={{
            background:
              i.tone === "bad"
                ? "var(--color-danger-soft)"
                : i.tone === "warn"
                  ? "var(--color-warn-soft)"
                  : "var(--color-surface-2)",
          }}
        >
          <Icon name={i.icon ?? "alert"} size={14} />
          <span className="font-medium">{i.label}</span>
          {i.detail ? <span className="text-text-2">{i.detail}</span> : null}
        </li>
      ))}
    </ul>
  );
}

export { ConfidenceBadge };
