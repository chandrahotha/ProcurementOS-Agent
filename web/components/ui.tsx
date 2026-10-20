// Shared UI primitives (Slice 15): badge, card, stat, progress, empty state,
// skeleton, field, section. Tailwind utilities + the token layer in globals.css.
import React from "react";
import { Icon, type IconName } from "@/components/icons";

export type Tone = "ok" | "warn" | "bad" | "info" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  ok: "badge-ok",
  warn: "badge-warn",
  bad: "badge-bad",
  info: "badge-info",
  neutral: "badge-neutral",
};

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: Tone;
  children: React.ReactNode;
}) {
  return <span className={`badge ${TONE_CLASS[tone]}`}>{children}</span>;
}

const STATE_TONE: Record<string, Tone> = {
  // Mission states + task/approval statuses map to display tones.
  intake: "info",
  plan: "info",
  evidence: "info",
  analysis: "info",
  scenarios: "info",
  negotiation: "warn",
  approval: "warn",
  action: "warn",
  report: "ok",
  queued: "neutral",
  running: "info",
  needs_review: "warn",
  blocked: "bad",
  done: "ok",
  failed: "bad",
  pending: "warn",
  approved: "ok",
  rejected: "bad",
  expired: "neutral",
  clean: "ok",
  quarantined: "warn",
  // An uncited AI draft: shown, but never dressed as a certified fact.
  stale: "warn",
  acknowledged: "ok",
  draft: "neutral",
  superseded: "neutral",
  ok: "ok",
  ALLOW: "ok",
  "NEEDS-APPROVAL": "warn",
  DENY: "bad",
  LOW: "ok",
  MEDIUM: "warn",
  HIGH: "bad",
  CRITICAL: "bad",
  active: "ok",
};

export function StateBadge({ state }: { state: string }) {
  return <Badge tone={STATE_TONE[state] ?? "neutral"}>{state}</Badge>;
}

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function StatCard({
  label,
  value,
  sub,
  icon,
  tone = "info",
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  icon?: IconName;
  tone?: Tone;
}) {
  return (
    <div className="card flex items-start gap-3">
      {icon ? (
        <span
          className={`badge ${TONE_CLASS[tone]} mt-0.5 shrink-0 rounded-lg p-2`}
        >
          <Icon name={icon} size={16} />
        </span>
      ) : null}
      <div className="min-w-0">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-text-2">
          {label}
        </div>
        <div className="mono mt-1 truncate text-2xl font-semibold">{value}</div>
        {sub ? <div className="mt-0.5 text-xs text-text-2">{sub}</div> : null}
      </div>
    </div>
  );
}

export function Progress({ pct, tone = "info" }: { pct: number; tone?: Tone }) {
  const fill =
    tone === "ok" ? "bg-ok" : tone === "warn" ? "bg-warn" : tone === "bad" ? "bg-danger" : "bg-accent";
  return (
    <div
      className="h-2 w-full min-w-24 overflow-hidden rounded-full"
      style={{ background: "var(--color-surface-2)" }}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full rounded-full transition-all duration-300 ${fill}`}
        style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
      />
    </div>
  );
}

export function EmptyState({
  icon = "document",
  title,
  body,
  action,
}: {
  icon?: IconName;
  title: string;
  body?: React.ReactNode;
  action?: { label: string; href: string };
}) {
  return (
    <div className="card flex flex-col items-center gap-3 py-12 text-center">
      <span
        className="flex h-12 w-12 items-center justify-center rounded-full"
        style={{ background: "var(--color-accent-soft)", color: "var(--color-accent)" }}
      >
        <Icon name={icon} size={22} />
      </span>
      <div className="text-sm font-semibold">{title}</div>
      {body ? <div className="max-w-md text-sm text-text-2">{body}</div> : null}
      {action ? (
        <a
          href={action.href}
          className="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-transparent px-3.5 py-2 text-sm font-medium text-white transition-all"
          style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-accent-2))" }}
        >
          {action.label}
        </a>
      ) : null}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return <label>{label}{children}</label>;
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 text-sm font-semibold tracking-tight">{children}</h2>
  );
}
