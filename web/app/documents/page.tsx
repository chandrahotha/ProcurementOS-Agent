// G07 Documents Library, wired (F30): aggregates api.documents across live
// missions with quarantine status and links to the mission intake.
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen } from "@/components/Screen";
import { api, stateForError, type Mission } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StatCard, StateBadge } from "@/components/ui";

type Doc = { id: string; filename: string; status: string; mission: Mission };

export default function DocumentsPage() {
  const [rows, setRows] = useState<Doc[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    const t = readToken();
    if (!t) {
      setState("empty");
      return;
    }
    api.missions(t)
      .then(async (d) => {
        const missions = d.missions.slice(0, 20);
        const docs = await Promise.all(
          missions.map(async (m) => {
            try {
              const dd = await api.documents(m.id, t);
              return dd.documents.map((x) => ({ ...x, mission: m }));
            } catch {
              return [];
            }
          }),
        );
        setRows(docs.flat());
        setState(docs.flat().length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  const quarantined = rows.filter((r) => r.status === "quarantined");
  const rejected = rows.filter((r) => r.status === "rejected");

  return (
    <Screen code="G07" title="Documents Library" breadcrumb={[{ label: "Workspace" }, { label: "Documents" }]}
      status="Across live missions, newest first" state={state}>
      {state === "success" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Documents" value={rows.length} icon="document" />
            <StatCard label="Quarantined" value={quarantined.length} icon="shield"
              tone={quarantined.length ? "warn" : "ok"} />
            <StatCard label="Rejected" value={rejected.length} icon="alert"
              tone={rejected.length ? "bad" : "ok"} />
          </div>
          {rows.length === 0 ? (
            <EmptyState icon="document" title="No documents yet"
              body="Upload quotes and contracts from each mission's Intake screen — they appear here tenant-wide."
              action={{ label: "Go to Mission Control", href: "/agent" }} />
          ) : (
            <div className="table-card">
              <table>
                <caption className="sr-only">Documents across missions</caption>
                <thead>
                  <tr><th scope="col">File</th><th scope="col">Status</th><th scope="col">Mission</th></tr>
                </thead>
                <tbody>
                  {rows.map((d) => (
                    <tr key={`${d.mission.id}-${d.id}`}>
                      <td data-label="File" className="font-medium">{d.filename}</td>
                      <td data-label="Status"><StateBadge state={d.status} /></td>
                      <td data-label="Mission">
                        <Link href={`/agent/${d.mission.id}/intake`} className="mono text-accent hover:underline">
                          {d.mission.title}
                        </Link>
                      </td>
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
