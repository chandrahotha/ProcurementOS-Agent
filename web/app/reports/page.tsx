// G11 Reports, wired (F34): export history from real audit events
// (report_exported) — persisted server-side, re-downloadable per mission.
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StatCard } from "@/components/ui";

type Event = { id: string; action: string; mission_id: string | null;
  request_id: string; reason: string | null; at: string };

export default function ReportsPage() {
  const [rows, setRows] = useState<Event[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    api.audit(readToken())
      .then((d) => {
        setRows(d.events.filter((e) => e.action === "report_exported"));
        setState("success");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  return (
    <Screen code="G11" title="Reports" breadcrumb={[{ label: "Workspace" }, { label: "Reports" }]}
      status="Export history from the audit trail, newest first" state={state}>
      {state === "success" ? (
        <>
          <StatCard label="Exports" value={rows.length} icon="document" />
          {rows.length === 0 ? (
            <EmptyState icon="document" title="No exports yet"
              body="Export a mission report from the Report screen (P16) — exports land in the audit trail with their manifest."
              action={{ label: "Go to Mission Control", href: "/agent" }} />
          ) : (
            <div className="table-card">
              <table>
                <caption className="sr-only">Export history</caption>
                <thead>
                  <tr><th scope="col">At</th><th scope="col">Mission</th><th scope="col">Request</th></tr>
                </thead>
                <tbody>
                  {rows.map((e) => (
                    <tr key={e.id}>
                      <td data-label="At" className="mono">{e.at.slice(0, 19)}</td>
                      <td data-label="Mission">
                        {e.mission_id ? (
                          <Link href={`/agent/${e.mission_id}/report`} className="mono text-accent hover:underline">
                            {e.mission_id.slice(0, 8)}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td data-label="Request" className="mono">{e.request_id.slice(0, 12)}…</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
      {state === "denied" || state === "empty" ? (
        <EmptyState icon="lock" title="Not available"
          body="Connect a token on Mission Control first."
          action={{ label: "Go to Mission Control", href: "/agent" }} />
      ) : null}
    </Screen>
  );
}
