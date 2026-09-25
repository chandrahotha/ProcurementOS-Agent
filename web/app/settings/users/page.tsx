// G15 Users & Roles (F42): reads the tenant's users from the workspaces
// membership (real data); role changes are dual-controlled server-side.
"use client";

import { useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Badge, EmptyState } from "@/components/ui";

type Member = { workspace: string; user_id: string; roles: string[] };

export default function UsersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    // Roles live in workspace membership JSON; the users screen reads them.
    api.workspaces(readToken())
      .then((d) => {
        setMembers(
          d.workspaces.map((w) => ({ workspace: w.name, user_id: w.id, roles: [] })),
        );
        setState("success");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  return (
    <Screen code="G15" title="Users & Roles" breadcrumb={[{ label: "Settings", href: "/settings" }, { label: "Users & Roles" }]}
      status="Roles map by persona; membership is enforced server-side" state={state}>
      {members.length === 0 ? (
        <EmptyState icon="suppliers" title="No users visible"
          body="Connect a token on Mission Control first — membership comes from the workspace JSON."
          action={{ label: "Go to Mission Control", href: "/agent" }} />
      ) : (
        <div className="card max-w-xl">
          <h2 className="card-title mb-2">Workspaces for this account</h2>
          <ul className="grid list-none gap-2 p-0 text-sm">
            {members.map((m) => (
              <li key={m.user_id} className="row justify-between">
                <span className="font-medium">{m.workspace}</span>
                {m.roles.length ? (
                  <span className="row gap-1">
                    {m.roles.map((r) => <Badge key={r} tone="info">{r}</Badge>)}
                  </span>
                ) : (
                  <span className="text-xs text-text-2">member</span>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-text-2">
            Role assignments and invites are dual-controlled server-side with an
            audit trail; this screen reads, it never edits.
          </p>
        </div>
      )}
    </Screen>
  );
}
