// G05 Notifications, wired (F32): derived feed from real rows — pending
// approvals, gate rejections — newest first. GET /notifications exists (B48).
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Badge, EmptyState, StatCard } from "@/components/ui";

type Note = { kind: string; title: string; mission_id: string | null; at: string };

export default function NotificationsPage() {
  const [rows, setRows] = useState<Note[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    api.notifications(readToken())
      .then((d) => {
        setRows(d.notifications);
        setState(d.notifications.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  const pending = rows.filter((r) => r.kind === "approval_pending");

  return (
    <Screen code="G05" title="Notifications" breadcrumb={[{ label: "Trust" }, { label: "Notifications" }]}
      status="Pending approvals and gate rejections, newest first" state={state}>
      {state === "success" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <StatCard label="Total" value={rows.length} icon="bell" />
            <StatCard label="Awaiting decisions" value={pending.length} icon="shield"
              tone={pending.length ? "warn" : "ok"} />
          </div>
          {rows.length === 0 ? (
            <EmptyState icon="check" title="Nothing needs attention"
              body="Pending approvals and gate rejections appear here as missions move." />
          ) : (
            <div className="grid gap-2">
              {rows.map((n, i) => (
                <div key={`${n.at}-${i}`} className="card row flex-wrap items-center justify-between gap-3 py-3">
                  <div className="row min-w-0 gap-3">
                    <Badge tone={n.kind === "approval_pending" ? "warn" : "bad"}>{n.kind}</Badge>
                    <span className="min-w-0 truncate text-sm">{n.title}</span>
                  </div>
                  <div className="row gap-3 text-xs text-text-2">
                    {n.mission_id ? (
                      <Link href={`/agent/${n.mission_id}`} className="mono text-accent hover:underline">
                        {n.mission_id.slice(0, 8)}
                      </Link>
                    ) : null}
                    <span className="mono">{n.at.slice(0, 19)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : null}
      {state === "denied" || state === "empty" ? (
        <EmptyState icon="bell" title="No notifications"
          body="Connect a token on Mission Control first."
          action={{ label: "Go to Mission Control", href: "/agent" }} />
      ) : null}
    </Screen>
  );
}
