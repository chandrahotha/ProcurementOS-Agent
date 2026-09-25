// G19 Security & Privacy (F42): session posture from real audit login data;
// the dev-token fallback is dev/test only and unreachable with OIDC.
"use client";

import { useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Card, EmptyState, StatCard } from "@/components/ui";

type Event = { id: string; action: string; actor_id: string | null; at: string };

export default function SecurityPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    api.audit(readToken())
      .then((d) => {
        setEvents(d.events.filter((e) => e.action.includes("denied") || e.action.includes("blocked")));
        setState("success");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  return (
    <Screen code="G19" title="Security & Privacy" breadcrumb={[{ label: "Settings", href: "/settings" }, { label: "Security" }]}
      status="Deny-by-default RBAC, hash-chained audit, OIDC in production" state={state}>
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard label="Gate denials" value={events.length} icon="alert"
          tone={events.length ? "warn" : "ok"} />
        <StatCard label="Auth" value="OIDC" icon="lock" tone="ok" sub="dev fallback fenced" />
        <StatCard label="Audit" value="chained" icon="shield" tone="ok" sub="tamper-evident" />
      </div>
      {state === "success" && events.length === 0 ? (
        <EmptyState icon="lock" title="No security events"
          body="Gate denials and blocks appear here from the audit trail." />
      ) : null}
      {state === "success" && events.length > 0 ? (
        <Card>
          <h2 className="card-title mb-2">Recent denials</h2>
          <ul className="grid list-none gap-1.5 p-0 text-sm">
            {events.slice(0, 8).map((e) => (
              <li key={e.id} className="row justify-between">
                <span>{e.action}</span>
                <span className="mono text-xs text-text-2">{e.at.slice(0, 19)}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
      <p className="max-w-xl text-xs text-text-2">
        Session review and revocation are enforced server-side; tokens are
        stored hashed and the dev fallback is unreachable once OIDC is wired.
      </p>
    </Screen>
  );
}
