// G13 Audit Log, wired: tenant-wide hash-chained events, newest first.
// Read-only by contract; a dedicated audit-read role can never mutate.
"use client";

import { useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Event = { id: string; action: string; object_type: string;
  mission_id: string | null; actor_id: string | null; request_id: string;
  reason: string | null; event_hash: string; at: string };

export default function AuditPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [state, setState] = useState<"empty" | "success" | "denied">("empty");

  useEffect(() => {
    api.audit(readToken())
      .then((d) => {
        setEvents(d.events);
        setState(d.events.length ? "success" : "empty");
      })
      .catch(() => setState("denied"));
  }, []);

  return (
    <Screen code="G13" title="Audit Log" breadcrumb="Audit" primary="Export audit"
      state={state}>
      {state === "denied" ? (
        <p>Not available. Connect a token on Mission Control first.</p>
      ) : events.length === 0 ? (
        <p>No events yet — they appear as missions move.</p>
      ) : (
        <table>
          <thead>
            <tr><th>At</th><th>Action</th><th>Object</th><th>Mission</th><th>Actor</th><th>Hash</th></tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td className="mono">{e.at.slice(0, 19)}</td>
                <td>{e.action}</td>
                <td>{e.object_type}</td>
                <td className="mono">{e.mission_id?.slice(0, 8) ?? "—"}</td>
                <td className="mono">{e.actor_id?.slice(0, 8) ?? "system"}</td>
                <td className="mono">{e.event_hash}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Screen>
  );
}
