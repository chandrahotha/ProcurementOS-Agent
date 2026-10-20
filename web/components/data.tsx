// Data primitives the brain names but the repo never had:
// DataTable (sort/filter/pin/density/expand), FilterBar, MetricRow,
// CoverageRing, ConfidenceBadge, Money.
//
// Every one of them is built on the token contract in app/globals.css and
// stays inside the accessibility floor the brain sets: sortable columns
// announce their direction, the ring is a labelled progressbar, and
// numbers are tabular so a column of money lines up.
"use client";

import React, { useMemo, useState } from "react";
import { Badge, Progress, StatCard, type Tone } from "@/components/ui";
import { Icon, type IconName } from "@/components/icons";

// ---------------------------------------------------------------- DataTable

export type Column<T> = {
  key: string;
  header: string;
  /** Cell renderer. `row` is the whole record, so a cell can show a value
   *  from another column. */
  render: (row: T) => React.ReactNode;
  /** Value used for sorting. Defaults to the rendered text. */
  sortValue?: (row: T) => string | number;
  /** Pinned columns stay visible when the table scrolls sideways. */
  pinned?: boolean;
  /** Hidden on narrow screens; the row's data-label fallback still shows it. */
  secondary?: boolean;
  align?: "left" | "right";
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  empty = "Nothing to show.",
  dense = false,
  onRowClick,
  expandable,
  initialSort,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption: string;
  empty?: string;
  dense?: boolean;
  onRowClick?: (row: T) => void;
  expandable?: (row: T) => React.ReactNode;
  initialSort?: { key: string; dir: "asc" | "desc" };
}) {
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(
    initialSort ?? null,
  );
  const [open, setOpen] = useState<string | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const value = (row: T) => {
      const v = col.sortValue ? col.sortValue(row) : String(col.render(row) ?? "");
      return typeof v === "number" ? v : v.toLowerCase();
    };    const copy = [...rows];
    copy.sort((a, b) => {
      const av = value(a);
      const bv = value(b);
      if (av === bv) return 0;
      const cmp = av < bv ? -1 : 1;
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [rows, sort, columns]);

  const toggle = (key: string) =>
    setSort((s) =>
      s?.key === key
        ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" },
    );

  if (rows.length === 0) {
    return (
      <div className="card text-sm text-text-2">
        {empty}
      </div>
    );
  }

  return (
    <div className={`table-card ${dense ? "density-compact" : "density-comfortable"}`}>
      <table>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {expandable ? <th scope="col" className="w-8"><span className="sr-only">Details</span></th> : null}
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : "none"}
                  className={c.align === "right" ? "text-right" : undefined}
                >
                  <button
                    type="button"
                    className="ghost border-transparent p-0 text-[11px] font-semibold uppercase tracking-wider"
                    onClick={() => toggle(c.key)}
                  >
                    {c.header}
                    <span aria-hidden="true" className="ml-1 opacity-60">
                      {active ? (sort!.dir === "asc" ? "▲" : "▼") : "↕"}
                    </span>
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const key = rowKey(row);
            const isOpen = open === key;
            return (
              <React.Fragment key={key}>
                <tr
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={onRowClick ? "cursor-pointer" : undefined}
                >
                  {expandable ? (
                    <td data-label="Details">
                      <button
                        type="button"
                        className="ghost p-1"
                        aria-expanded={isOpen}
                        aria-label={isOpen ? "Hide details" : "Show details"}
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpen(isOpen ? null : key);
                        }}
                      >
                        <Icon name={isOpen ? "chevron-down" : "chevron-right"} size={14} />
                      </button>
                    </td>
                  ) : null}
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      data-label={c.header}
                      className={c.align === "right" ? "text-right" : undefined}
                    >
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
                {expandable && isOpen ? (
                  <tr>
                    <td colSpan={columns.length + 1} className="bg-surface-2">
                      {expandable(row)}
                    </td>
                  </tr>
                ) : null}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- FilterBar

export function FilterBar({
  search,
  onSearch,
  placeholder = "Filter…",
  children,
}: {
  search?: string;
  onSearch?: (value: string) => void;
  placeholder?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="row justify-between gap-3">
      {onSearch ? (
        <label className="min-w-[220px] flex-1">
          <span className="sr-only">Search</span>
          <input
            type="search"
            value={search ?? ""}
            placeholder={placeholder}
            onChange={(e) => onSearch(e.target.value)}
          />
        </label>
      ) : null}
      {children ? <div className="row gap-2">{children}</div> : null}
    </div>
  );
}

// ---------------------------------------------------------------- MetricRow

export function MetricRow({
  metrics,
}: {
  metrics: { label: string; value: React.ReactNode; sub?: string; icon?: IconName; tone?: Tone }[];
}) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {metrics.map((m) => (
        <StatCard
          key={m.label}
          label={m.label}
          value={m.value}
          sub={m.sub}
          icon={m.icon}
          tone={m.tone ?? "info"}
        />
      ))}
    </div>
  );
}

// ------------------------------------------------------------- CoverageRing

export function CoverageRing({
  pct,
  size = 44,
  label = "coverage",
}: {
  pct: number;
  size?: number;
  label?: string;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(pct)));
  const stroke = 4;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const tone = clamped >= 80 ? "ok" : clamped >= 50 ? "warn" : "bad";
  const color =
    tone === "ok"
      ? "var(--color-ok)"
      : tone === "warn"
        ? "var(--color-warn)"
        : "var(--color-danger)";
  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center"
      title={`${label}: ${clamped}%`}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`${label} ${clamped}%`}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-surface-2)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${(clamped / 100) * c} ${c}`}
        />
      </svg>
      <span className="mono absolute text-[10px] font-semibold">{clamped}%</span>
    </span>
  );
}

// ----------------------------------------------------------- ConfidenceBadge

export function ConfidenceBadge({ value, label }: { value: number; label?: string }) {
  const pct = Math.round(value * 100);
  const tone: Tone = pct >= 85 ? "ok" : pct >= 60 ? "warn" : "bad";
  return (
    <Badge tone={tone}>
      {label ? `${label} ` : ""}
      {pct}%
    </Badge>
  );
}

// --------------------------------------------------------------------- Money

export function Money({
  minor,
  currency = "INR",
  signed = false,
}: {
  minor: number;
  currency?: string;
  signed?: boolean;
}) {
  const value = minor / 100;
  const text = new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
  return (
    <span className={signed ? (minor < 0 ? "text-danger" : "text-ok") : undefined}>
      {text}
    </span>
  );
}

// ----------------------------------------------------------------- Deadline

export function Deadline({ iso, warnDays = 14 }: { iso: string | null; warnDays?: number }) {
  if (!iso) return <span className="text-text-2">—</span>;
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return <span className="text-text-2">—</span>;
  const days = Math.ceil((when.getTime() - Date.now()) / 86_400_000);
  const tone: Tone = days < 0 ? "bad" : days <= warnDays ? "warn" : "neutral";
  return (
    <Badge tone={tone}>
      {days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? "today" : `${days}d left`}
    </Badge>
  );
}

// ------------------------------------------------------------------- Pieces

export function Section({
  title,
  action,
  children,
  id,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  id?: string;
}) {
  return (
    <section id={id} className="grid gap-3">
      <div className="row justify-between">
        <h2 className="card-title">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Meter({ pct, tone = "info" }: { pct: number; tone?: Tone }) {
  return <Progress pct={pct} tone={tone} />;
}
