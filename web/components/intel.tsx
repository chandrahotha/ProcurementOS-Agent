// The intelligence visualisations the brain specifies and the repo never
// built: CostWaterfall, RiskHeatmap, NegotiationLadder, ScoreBreakdown,
// ScenarioCard.
//
// Each one is drawn from the *certified* numbers the API returns. None of
// them computes anything: a visualisation that recalculated would be a
// second source of truth, and the whole point of this product is that the
// deterministic engine decides and the screen only shows it.
"use client";

import React from "react";
import { Badge, type Tone } from "@/components/ui";
import { Icon } from "@/components/icons";
import { Money } from "@/components/data";

// ------------------------------------------------------------ CostWaterfall

export type CostBuildUp = {
  supplier_id: string;
  tco_minor: number;
  build_up: Record<string, number>;
  fx?: unknown[];
  stale?: boolean;
  currency?: string;
};

const SEGMENTS: { key: string; label: string; tone: Tone }[] = [
  { key: "price", label: "Price", tone: "info" },
  { key: "freight", label: "Freight", tone: "neutral" },
  { key: "insurance", label: "Insurance", tone: "neutral" },
  { key: "tooling", label: "Tooling", tone: "neutral" },
  { key: "tax", label: "Tax", tone: "warn" },
  { key: "discounts", label: "Discounts", tone: "ok" },
];

const SEGMENT_COLOR: Record<Tone, string> = {
  ok: "var(--color-ok)",
  warn: "var(--color-warn)",
  bad: "var(--color-danger)",
  info: "var(--color-accent)",
  neutral: "var(--color-text-2)",
};

export function CostWaterfall({
  costs,
  currency = "INR",
  onSelect,
}: {
  costs: CostBuildUp[];
  currency?: string;
  onSelect?: (supplierId: string) => void;
}) {
  if (costs.length === 0) {
    return <p className="text-sm text-text-2">No TCO rows yet.</p>;
  }
  const max = Math.max(...costs.map((c) => Math.abs(c.tco_minor)), 1);
  return (
    <div className="grid gap-3">
      {costs.map((c) => {
        const segments = SEGMENTS.map((s) => ({
          ...s,
          value: Math.abs(Number(c.build_up?.[s.key] ?? 0)),
        })).filter((s) => s.value > 0);
        const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
        return (
          <div key={c.supplier_id} className="grid gap-1.5">
            <div className="row justify-between">
              <button
                type="button"
                className="ghost p-0 text-sm font-semibold"
                onClick={() => onSelect?.(c.supplier_id)}
              >
                {c.supplier_id}
              </button>
              <span className="row gap-2">
                {c.stale ? <Badge tone="warn">stale FX</Badge> : null}
                <span className="mono text-sm font-semibold">
                  <Money minor={c.tco_minor} currency={currency} />
                </span>
              </span>
            </div>
            <div
              className="flex h-6 w-full overflow-hidden rounded-lg"
              style={{ background: "var(--color-surface-2)" }}
              role="img"
              aria-label={`${c.supplier_id} total cost of ownership ${Math.round(
                (c.tco_minor / max) * 100,
              )}% of the highest`}
            >
              {segments.map((s) => (
                <span
                  key={s.key}
                  title={`${s.label}: ${s.value} minor`}
                  style={{
                    width: `${(s.value / total) * 100}%`,
                    background: SEGMENT_COLOR[s.tone],
                  }}
                />
              ))}
            </div>
            <div className="row flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-2">
              {segments.map((s) => (
                <span key={s.key} className="row gap-1">
                  <span
                    aria-hidden="true"
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: SEGMENT_COLOR[s.tone] }}
                  />
                  {s.label} <span className="mono"><Money minor={s.value} currency={currency} /></span>
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// -------------------------------------------------------------- RiskHeatmap

export type RiskRow = {
  supplier_id: string;
  dimensions: Record<string, number>;
  composite: number;
  band: string;
  weights_version?: string;
};

const DIMENSION_LABELS: Record<string, string> = {
  quality: "Quality",
  delivery: "Delivery",
  financial: "Financial",
  compliance: "Compliance",
  geo: "Geo",
};

export function RiskHeatmap({
  risks,
  onCell,
}: {
  risks: RiskRow[];
  onCell?: (supplierId: string, dimension: string) => void;
}) {
  if (risks.length === 0) {
    return <p className="text-sm text-text-2">No risk rows yet.</p>;
  }
  const dimensions = Array.from(
    new Set(risks.flatMap((r) => Object.keys(r.dimensions ?? {}))),
  );
  // The dimension values are RISK scores, not quality scores: the engine
  // maps a high weighted composite to a worse band (the golden vector pins
  // composite 10 -> LOW and composite 90 -> CRITICAL), so a high cell is
  // red. Colouring it the other way would contradict the band column on
  // the same row.
  const cellTone = (v: number): Tone =>
    v >= 75 ? "bad" : v >= 50 ? "warn" : v >= 25 ? "neutral" : "ok";
  return (
    <div className="table-card">
      <table>
        <caption className="sr-only">
          Risk score by supplier and dimension, 0 to 100 where higher is worse
        </caption>
        <thead>
          <tr>
            <th scope="col">Supplier</th>
            {dimensions.map((d) => (
              <th key={d} scope="col" className="text-right">
                {DIMENSION_LABELS[d] ?? d}
              </th>
            ))}
            <th scope="col" className="text-right">
              Composite
            </th>
            <th scope="col">Band</th>
          </tr>
        </thead>
        <tbody>
          {risks.map((r) => (
            <tr key={r.supplier_id}>
              <td data-label="Supplier" className="font-medium">
                {r.supplier_id}
              </td>
              {dimensions.map((d) => {
                const v = Number(r.dimensions?.[d] ?? 0);
                const tone = cellTone(v);
                return (
                  <td key={d} data-label={DIMENSION_LABELS[d] ?? d} className="text-right">
                    <button
                      type="button"
                      className="ghost p-0"
                      onClick={() => onCell?.(r.supplier_id, d)}
                      title={`${DIMENSION_LABELS[d] ?? d}: ${v} (higher is worse)`}
                    >
                      <Badge tone={tone}>{v}</Badge>
                    </button>
                  </td>
                );
              })}
              <td data-label="Composite" className="mono text-right font-semibold">
                {r.composite}
              </td>
              <td data-label="Band">
                <Badge
                  tone={
                    r.band === "LOW"
                      ? "ok"
                      : r.band === "MEDIUM"
                        ? "warn"
                        : r.band === "HIGH"
                          ? "bad"
                          : "bad"
                  }
                >
                  {r.band}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --------------------------------------------------------- NegotiationLadder

export type Ladder = {
  opening: number;
  target: number;
  walk_away: number;
  concessions?: number[];
};

export function NegotiationLadder({
  ladder,
  draftPrice,
  candidateCost,
  batnaCost,
  currency = "INR",
}: {
  ladder: Ladder;
  draftPrice?: number;
  candidateCost?: number;
  batnaCost?: number;
  currency?: string;
}) {
  const points: { label: string; value: number; tone: Tone; note?: string }[] = [
    { label: "Walk-away", value: ladder.walk_away, tone: "bad", note: "hard wall" },
    { label: "Target", value: ladder.target, tone: "ok", note: "aim here" },
    { label: "Opening", value: ladder.opening, tone: "info" },
  ];
  if (candidateCost) {
    points.push({ label: "Our cost", value: candidateCost, tone: "neutral" });
  }
  if (batnaCost) {
    points.push({ label: "BATNA", value: batnaCost, tone: "neutral" });
  }
  const min = Math.min(...points.map((p) => p.value));
  const max = Math.max(...points.map((p) => p.value)) || 1;
  const pos = (v: number) => ((v - min) / (max - min || 1)) * 100;

  return (
    <div className="grid gap-3">
      <div className="relative h-2 w-full rounded-full" style={{ background: "var(--color-surface-2)" }}>
        {points.map((p) => (
          <span
            key={p.label}
            className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white"
            style={{
              left: `${pos(p.value)}%`,
              background: SEGMENT_COLOR[p.tone],
            }}
            title={`${p.label}: ${p.value} minor`}
          />
        ))}
        {draftPrice != null ? (
          <span
            className="absolute top-1/2 h-6 w-1 -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${pos(draftPrice)}%`, background: "var(--color-text)" }}
            title={`Draft: ${draftPrice} minor`}
          />
        ) : null}
      </div>
      <div className="row flex-wrap gap-x-4 gap-y-1 text-[11px] text-text-2">
        {points.map((p) => (
          <span key={p.label} className="row gap-1">
            <span
              aria-hidden="true"
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: SEGMENT_COLOR[p.tone] }}
            />
            {p.label} <span className="mono"><Money minor={p.value} currency={currency} /></span>
            {p.note ? <span className="opacity-70">({p.note})</span> : null}
          </span>
        ))}
        {draftPrice != null ? (
          <span className="row gap-1">
            <span aria-hidden="true" className="inline-block h-3 w-0.5 bg-text" />
            Draft <span className="mono"><Money minor={draftPrice} currency={currency} /></span>
          </span>
        ) : null}
      </div>
    </div>
  );
}

// ----------------------------------------------------------- ScoreBreakdown

export type Criterion = { name: string; weight: number; score: number; note?: string };

/**
 * The certified scorecard, shown as weighted contributions.
 *
 * There is deliberately no editing control. A what-if slider that
 * recomputed a score in the browser would be a second source of truth
 * next to the certified one, and the brain is explicit that an analytical
 * recomputation must be labelled as such and must never overwrite a
 * certified score. A sandbox recomputation is a *server* capability that
 * would recompute against the pinned rule version and label the result
 * analytical; it is specified in the product brain and is listed as
 * proposed in `docs/EVALUATION.md`, not implemented here.
 */
export function ScoreBreakdown({ criteria }: { criteria: Criterion[] }) {
  if (criteria.length === 0) {
    return <p className="text-sm text-text-2">No scorecard yet.</p>;
  }
  return (
    <ul className="grid list-none gap-2 p-0">
      {criteria.map((c) => {
        const weighted = c.weight * c.score;
        const tone: Tone = c.score >= 80 ? "ok" : c.score >= 50 ? "warn" : "bad";
        return (
          <li key={c.name} className="grid gap-1">
            <div className="row justify-between text-sm">
              <span className="row gap-2">
                {c.name}
                <span className="text-[11px] text-text-2">
                  weight {Math.round(c.weight * 100)}%
                </span>
              </span>
              <span className="mono">
                {c.score} → {weighted.toFixed(1)}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--color-surface-2)" }}>
              <div
                className="h-full rounded-full"
                style={{ width: `${Math.max(0, Math.min(100, c.score))}%`, background: SEGMENT_COLOR[tone] }}
              />
            </div>
            {c.note ? <p className="text-[11px] text-text-2">{c.note}</p> : null}
          </li>
        );
      })}
    </ul>
  );
}

// -------------------------------------------------------------- ScenarioCard

export type ScenarioOut = {
  scenario_id: string;
  allocations: { supplier_id: string; qty: number; unit_cost_minor?: number }[];
  objective_value: number;
  savings_vs_baseline: number;
  candidate: boolean;
  constraints_ok?: boolean;
};

export function ScenarioCard({
  scenario,
  currency = "INR",
  onMarkCandidate,
  canMarkCandidate = false,
}: {
  scenario: ScenarioOut;
  currency?: string;
  onMarkCandidate?: (scenarioId: string) => void;
  canMarkCandidate?: boolean;
}) {
  return (
    <div className="card grid gap-3">
      <div className="row justify-between">
        <span className="row gap-2">
          <Icon name="layers" size={14} />
          <strong className="text-sm">{scenario.scenario_id}</strong>
          {scenario.candidate ? <Badge tone="ok">candidate</Badge> : null}
          {scenario.constraints_ok === false ? <Badge tone="bad">infeasible</Badge> : null}
        </span>
        <span className="mono text-sm font-semibold">
          <Money minor={scenario.objective_value} currency={currency} />
        </span>
      </div>
      <div className="table-card">
        <table>
          <caption className="sr-only">Allocation for {scenario.scenario_id}</caption>
          <thead>
            <tr>
              <th scope="col">Supplier</th>
              <th scope="col" className="text-right">
                Qty
              </th>
              <th scope="col" className="text-right">
                Unit cost
              </th>
            </tr>
          </thead>
          <tbody>
            {scenario.allocations.map((a, i) => (
              <tr key={`${a.supplier_id}-${i}`}>
                <td data-label="Supplier">{a.supplier_id}</td>
                <td data-label="Qty" className="mono text-right">
                  {a.qty}
                </td>
                <td data-label="Unit cost" className="mono text-right">
                  {a.unit_cost_minor ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="row justify-between">
        <span className="row gap-2 text-sm">
          <span className="text-text-2">Savings vs baseline</span>
          <Money minor={scenario.savings_vs_baseline} currency={currency} signed />
        </span>
        {canMarkCandidate && onMarkCandidate && !scenario.candidate ? (
          <button type="button" onClick={() => onMarkCandidate(scenario.scenario_id)}>
            Mark as candidate
          </button>
        ) : null}
      </div>
    </div>
  );
}
