// G06 Global Search, wired (F36): real search over live missions with a
// client-side filter + links into each mission's evidence.
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen } from "@/components/Screen";
import { api, stateForError, type Mission } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";
import { Icon } from "@/components/icons";

export default function SearchPage() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [q, setQ] = useState("");
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    api.missions(readToken())
      .then((d) => {
        setMissions(d.missions);
        setState("success");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  const ql = q.trim().toLowerCase();
  const hits = missions.filter(
    (m) =>
      !ql ||
      m.title.toLowerCase().includes(ql) ||
      m.id.toLowerCase().includes(ql) ||
      m.state.toLowerCase().includes(ql),
  );

  return (
    <Screen code="G06" title="Global Search" breadcrumb={[{ label: "Mission" }, { label: "Search" }]}
      status="Missions, states, and ids — press / anywhere" state={state}>
      <div className="row max-w-xl gap-2">
        <span style={{ color: "var(--color-text-2)" }}>
          <Icon name="search" size={16} />
        </span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search missions…"
          aria-label="Search missions"
          className="flex-1"
        />
      </div>
      {state === "denied" || state === "empty" ? (
        <EmptyState icon="lock" title="Nothing to search"
          body="Connect a token on Mission Control first."
          action={{ label: "Go to Mission Control", href: "/agent" }} />
      ) : null}
      {state === "success" && hits.length === 0 ? (
        <EmptyState icon="search" title={`No matches for "${q}"`}
          body="Try a mission title, id, or state." />
      ) : null}
      {state === "success" && hits.length > 0 ? (
        <div className="table-card">
          <table>
            <caption className="sr-only">Search results</caption>
            <thead>
              <tr><th scope="col">Title</th><th scope="col">State</th><th scope="col">Id</th></tr>
            </thead>
            <tbody>
              {hits.map((m) => (
                <tr key={m.id}>
                  <td data-label="Title">
                    <Link href={`/agent/${m.id}/evidence`} className="font-medium hover:text-accent">
                      {m.title}
                    </Link>
                  </td>
                  <td data-label="State"><StateBadge state={m.state} /></td>
                  <td data-label="Id" className="mono">{m.id.slice(0, 8)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Screen>
  );
}
