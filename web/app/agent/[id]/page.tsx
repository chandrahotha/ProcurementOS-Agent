// Mission Overview (F18): details, timeline feed (F51), and every screen
// one click away. Deep links into /agent/<id> land here instead of 404.
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api, stateForError, type Mission } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StatCard } from "@/components/ui";

type Event = { kind: string; payload: Record<string, unknown>; at: string; actor: string | null };

export default function MissionOverview(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [mission, setMission] = useState<Mission | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [state, setState] = useState<"loading" | "success" | "error" | "denied">("loading");

  useEffect(() => {
    Promise.all([api.mission(id, readToken()), api.timeline(id, readToken())])
      .then(([m, t]) => {
        setMission(m);
        setEvents((t.events as Event[]).slice(-12).reverse());
        setState("success");
      })
      .catch((e) => setState(stateForError(e)));
  }, [id]);

  return (
    <Screen code="MO" title="Mission Overview" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: id.slice(0, 8) }]}
      status="Everything about this mission, one click away" state={state}>
      {state === "denied" ? (
        <EmptyState
          icon="lock"
          title="No access to this mission"
          body="It may belong to another tenant, or your token lacks the workspace membership."
          action={{ label: "Go to Mission Control", href: "/agent" }}
        />
      ) : null}
      {state === "success" && mission ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="State" value={mission.state} icon="mission" />
            <StatCard label="Coverage" value={`${mission.coverage_pct}%`} icon="chart" />
            <StatCard label="Dial" value={mission.autonomy_level} icon="settings" />
            <StatCard label="Budget cap" value={mission.budget_cap_minor ?? 0} icon="document" sub={mission.currency} />
          </div>
          <section>
            <h2 className="mb-3 text-sm font-semibold tracking-tight">Timeline</h2>
            <div className="table-card">
              <table>
                <caption className="sr-only">Mission timeline events</caption>
                <thead>
                  <tr><th scope="col">At</th><th scope="col">Event</th><th scope="col">Actor</th></tr>
                </thead>
                <tbody>
                  {events.map((e, i) => (
                    <tr key={`${e.at}-${i}`}>
                      <td data-label="At" className="mono">{e.at.slice(0, 19)}</td>
                      <td data-label="Event">{e.kind}</td>
                      <td data-label="Actor" className="mono">{e.actor ?? "system"}</td>
                    </tr>
                  ))}
                  {events.length === 0 ? (
                    <tr><td colSpan={3}>No events yet.</td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </Screen>
  );
}
