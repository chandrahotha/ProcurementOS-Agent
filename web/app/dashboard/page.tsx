// G04 Dashboard, wired (F27): KPI cards from live missions + the audit tail,
// recent missions, latest events, exceptions. Real data only — never mocked.
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen } from "@/components/Screen";
import { api, stateForError, type Mission } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge, StatCard, type Tone } from "@/components/ui";

type AuditEvent = {
  id: string; action: string; mission_id: string | null; actor_id: string | null; at: string;
};

export default function DashboardPage() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [state, setState] = useState<"loading" | "success" | "error" | "denied" | "empty">("loading");

  useEffect(() => {
    const t = readToken();
    if (!t) {
      setState("empty");
      return;
    }
    Promise.all([api.missions(t), api.audit(t, 20)])
      .then(([m, a]) => {
        setMissions(m.missions);
        setEvents(a.events);
        setState(m.missions.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e)));
  }, []);

  const byState = new Map<string, number>();
  for (const m of missions) byState.set(m.state, (byState.get(m.state) ?? 0) + 1);
  const lowCoverage = missions.filter((m) => m.coverage_pct < 80);
  const recent = missions.slice(0, 5);

  return (
    <Screen code="G04" title="Dashboard" breadcrumb="Dashboard"
      status="Procurement at a glance" state={state}
      primary="New mission" primaryHref="/agent/new">
      {state === "empty" ? (
        <EmptyState
          icon="dashboard"
          title="No missions yet"
          body="Connect a token on Mission Control, then create your first mission — intake through report with approval gates on every material action."
          action={{ label: "Go to Mission Control", href: "/agent" }}
        />
      ) : null}
      {state === "success" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Missions" value={missions.length} icon="mission" />
            <StatCard
              label="In approval"
              value={byState.get("approval") ?? 0}
              icon="shield"
              tone={((byState.get("approval") ?? 0) > 0 ? "warn" : "ok") as Tone}
              sub="awaiting quorum"
            />
            <StatCard
              label="Completed"
              value={byState.get("report") ?? 0}
              icon="check"
              tone="ok"
            />
            <StatCard
              label="Exceptions"
              value={lowCoverage.length + events.filter((e) => e.action.includes("denied") || e.action.includes("blocked")).length}
              icon="alert"
              tone={(lowCoverage.length ? "warn" : "ok") as Tone}
              sub="low coverage + gate denials"
            />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <section>
              <h2 className="mb-3 text-sm font-semibold tracking-tight">Recent missions</h2>
              <div className="table-card">
                <table>
                  <caption className="sr-only">Recent missions</caption>
                  <thead>
                    <tr><th scope="col">Title</th><th scope="col">State</th><th scope="col">Coverage</th></tr>
                  </thead>
                  <tbody>
                    {recent.map((m) => (
                      <tr key={m.id}>
                        <td data-label="Title">
                          <Link href={`/agent/${m.id}`} className="font-medium hover:text-accent">
                            {m.title}
                          </Link>
                        </td>
                        <td data-label="State"><StateBadge state={m.state} /></td>
                        <td data-label="Coverage" className="mono">{m.coverage_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section>
              <h2 className="mb-3 text-sm font-semibold tracking-tight">Latest events</h2>
              <div className="table-card">
                <table>
                  <caption className="sr-only">Latest audit events</caption>
                  <thead>
                    <tr><th scope="col">At</th><th scope="col">Event</th></tr>
                  </thead>
                  <tbody>
                    {events.slice(0, 5).map((e) => (
                      <tr key={e.id}>
                        <td data-label="At" className="mono">{e.at.slice(0, 19)}</td>
                        <td data-label="Event">{e.action}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Link href="/audit" className="mt-2 inline-block text-xs font-medium text-accent hover:underline">
                Full audit log →
              </Link>
            </section>
          </div>
        </>
      ) : null}
    </Screen>
  );
}
