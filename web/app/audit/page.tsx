// G13 Audit Log, wired: tenant-wide hash-chained events, newest first.
// Read-only by contract; full hashes + prev_hash enable client-side chain
// verification (B34). Read-only by contract; a dedicated audit-read role
// can never mutate.
"use client";

import { useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Badge, EmptyState, StatCard } from "@/components/ui";

type Event = { id: string; action: string; object_type: string;
  mission_id: string | null; actor_id: string | null; request_id: string;
  reason: string | null; event_hash: string; prev_hash?: string; at: string };

export default function AuditPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [chain, setChain] = useState<{ intact: boolean; events_checked: number } | null>(null);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    Promise.all([api.audit(readToken()), api.auditVerify(readToken()).catch(() => null)])
      .then(([d, v]) => {
        setEvents(d.events);
        setChain(v);
        setState(d.events.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  const denials = events.filter((e) => e.action.includes("denied") || e.action.includes("blocked"));

  return (
    <Screen code="G13" title="Audit Log" breadcrumb={[{ label: "Trust" }, { label: "Audit" }]}
      status="Hash-chained, newest first, read-only" state={state}>
      {state === "success" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Events" value={events.length} icon="shield" />
            <StatCard label="Gate denials" value={denials.length} icon="alert"
              tone={denials.length ? "warn" : "ok"} />
            <StatCard
              label="Chain"
              value={chain ? (chain.intact ? "intact" : "BROKEN") : "…"}
              icon="lock"
              tone={chain ? (chain.intact ? "ok" : "bad") : "neutral"}
              sub={chain ? `${chain.events_checked} links verified` : "verifying"}
            />
          </div>
          {events.length === 0 ? (
            <EmptyState icon="shield" title="No events yet"
              body="They appear as missions move." />
          ) : (
            <div className="table-card">
              <table>
                <caption className="sr-only">Audit events with chain hashes</caption>
                <thead>
                  <tr><th scope="col">At</th><th scope="col">Action</th><th scope="col">Object</th><th scope="col">Mission</th><th scope="col">Actor</th><th scope="col">Hash</th></tr>
                </thead>
                <tbody>
                  {events.map((e) => (
                    <tr key={e.id}>
                      <td data-label="At" className="mono">{e.at.slice(0, 19)}</td>
                      <td data-label="Action">
                        {e.action.includes("denied") || e.action.includes("blocked") ? (
                          <Badge tone="warn">{e.action}</Badge>
                        ) : (
                          e.action
                        )}
                      </td>
                      <td data-label="Object">{e.object_type}</td>
                      <td data-label="Mission" className="mono">{e.mission_id?.slice(0, 8) ?? "—"}</td>
                      <td data-label="Actor" className="mono">{e.actor_id?.slice(0, 8) ?? "system"}</td>
                      <td data-label="Hash" className="mono" title={e.event_hash}>{e.event_hash.slice(0, 12)}…</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
      {state === "denied" ? (
        <EmptyState icon="lock" title="Not available"
          body="Connect a token on Mission Control first."
          action={{ label: "Go to Mission Control", href: "/agent" }} />
      ) : null}
    </Screen>
  );
}
