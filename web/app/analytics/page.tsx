// AN Cross-Mission Analytics, wired (F29): aggregates from live missions —
// state distribution, coverage, autonomy mix. Real data only.
"use client";

import { useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api, stateForError, type Mission } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, Progress, StatCard } from "@/components/ui";

const STATES = ["intake", "plan", "evidence", "analysis", "scenarios",
  "negotiation", "approval", "action", "report"];

export default function AnalyticsPage() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    api.missions(readToken())
      .then((d) => {
        setMissions(d.missions);
        setState(d.missions.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  const byState = STATES.map((s) => ({ state: s, count: missions.filter((m) => m.state === s).length }));
  const maxCount = Math.max(1, ...byState.map((b) => b.count));
  const avgCoverage = missions.length
    ? Math.round(missions.reduce((a, m) => a + m.coverage_pct, 0) / missions.length)
    : 0;
  const dialMix = ["ASSISTED", "SUPERVISED", "GUARDED"].map((d) => ({
    dial: d,
    count: missions.filter((m) => m.autonomy_level === d).length,
  }));
  const gated = missions.filter((m) => ["negotiation", "approval", "action"].includes(m.state)).length;

  return (
    <Screen code="AN" title="Cross-Mission Analytics" breadcrumb={[{ label: "Mission" }, { label: "Analytics" }]}
      status="Derived from live mission rows — never mocked" state={state}>
      {state === "empty" ? (
        <EmptyState icon="chart" title="Nothing to analyze yet"
          body="Missions appear here as they move — connect a token and run some."
          action={{ label: "Go to Mission Control", href: "/agent" }} />
      ) : null}
      {state === "success" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Missions" value={missions.length} icon="mission" />
            <StatCard label="Avg coverage" value={`${avgCoverage}%`} icon="chart" />
            <StatCard label="Gated stages" value={gated} icon="shield" sub="negotiation → action" />
            <StatCard
              label="Completed"
              value={missions.filter((m) => m.state === "report").length}
              icon="check" tone="ok"
            />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="card">
              <h2 className="card-title mb-3">Missions by state</h2>
              <div className="grid gap-2.5">
                {byState.map((b) => (
                  <div key={b.state} className="row items-center gap-3 text-xs">
                    <span className="mono w-24 shrink-0">{b.state}</span>
                    <div className="flex-1">
                      <Progress pct={(b.count / maxCount) * 100} />
                    </div>
                    <span className="mono w-8 text-right">{b.count}</span>
                  </div>
                ))}
              </div>
            </section>
            <section className="card">
              <h2 className="card-title mb-3">Autonomy dial mix</h2>
              <div className="grid gap-2.5">
                {dialMix.map((d) => (
                  <div key={d.dial} className="row items-center gap-3 text-xs">
                    <span className="mono w-24 shrink-0">{d.dial}</span>
                    <div className="flex-1">
                      <Progress pct={(d.count / maxCount) * 100} tone="warn" />
                    </div>
                    <span className="mono w-8 text-right">{d.count}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </>
      ) : null}
    </Screen>
  );
}
