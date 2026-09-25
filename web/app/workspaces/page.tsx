// G03 Workspace Picker, wired (F39): GET /workspaces exists — real picker.
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";
import { Icon } from "@/components/icons";

type Workspace = { id: string; name: string; budget_currency: string };

export default function WorkspacesPage() {
  const [rows, setRows] = useState<Workspace[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    api.workspaces(readToken())
      .then((d) => {
        setRows(d.workspaces);
        setState(d.workspaces.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  return (
    <Screen code="G03" title="Workspace Picker" breadcrumb={[{ label: "Workspace" }, { label: "Workspaces" }]}
      status="Workspaces your account is a member of" state={state}>
      {state === "empty" ? (
        <EmptyState icon="suppliers" title="No workspaces"
          body="Connect a token on Mission Control first (demo tokens come from the synthetic seed)."
          action={{ label: "Go to Mission Control", href: "/agent" }} />
      ) : null}
      {state === "success" ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((w) => (
            <div key={w.id} className="card flex items-start gap-3">
              <span
                className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                style={{ background: "var(--color-accent-soft)", color: "var(--color-accent)" }}
              >
                <Icon name="suppliers" size={16} />
              </span>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold">{w.name}</div>
                <div className="mt-0.5 text-xs text-text-2">Budget in {w.budget_currency}</div>
                <Link href="/agent" className="mt-2 inline-block text-xs font-medium text-accent hover:underline">
                  Open missions →
                </Link>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {state === "denied" ? (
        <div className="card"><StateBadge state="quarantined" /> Membership is enforced server-side.</div>
      ) : null}
    </Screen>
  );
}
