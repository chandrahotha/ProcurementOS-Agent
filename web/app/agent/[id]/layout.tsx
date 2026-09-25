// Mission-scoped shell (F44): mission title + state + a tab bar linking the
// 14 mission screens, so no screen is reachable only by typing its URL.
// Keeps main[data-screen] codes on every child intact.
"use client";

import { useEffect, useState } from "react";
import { use } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { api, stateForError, type Mission } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { StateBadge } from "@/components/ui";

const SCREENS = [
  { seg: "", label: "Overview" },
  { seg: "intake", label: "Intake" },
  { seg: "plan", label: "Plan" },
  { seg: "tasks", label: "Tasks" },
  { seg: "evidence", label: "Evidence" },
  { seg: "suppliers", label: "Suppliers" },
  { seg: "cost", label: "Cost" },
  { seg: "risk", label: "Risk" },
  { seg: "scenarios", label: "Scenarios" },
  { seg: "negotiation", label: "Negotiation" },
  { seg: "decision", label: "Decision" },
  { seg: "approval", label: "Approval" },
  { seg: "actions", label: "Actions" },
  { seg: "runs", label: "Runs" },
  { seg: "report", label: "Report" },
];

export default function MissionLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const pathname = usePathname();
  const [mission, setMission] = useState<Mission | null>(null);

  useEffect(() => {
    api.mission(id, readToken())
      .then(setMission)
      .catch(() => setMission(null));
  }, [id]);

  const currentSeg = pathname.replace(`/agent/${id}`, "").replace(/^\//, "");

  return (
    <div className="grid gap-4">
      <div
        className="row flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3"
        style={{
          background: "linear-gradient(135deg, var(--color-accent-soft), transparent)",
          border: "1px solid var(--color-border)",
        }}
      >
        <div className="row min-w-0 items-center gap-3">
          {mission ? (
            <>
              <span className="truncate text-sm font-semibold tracking-tight">{mission.title}</span>
              <StateBadge state={mission.state} />
              <span className="mono text-xs text-text-2">{mission.coverage_pct}% coverage</span>
            </>
          ) : (
            <span className="skeleton h-5 w-56" />
          )}
        </div>
        <span className="mono text-xs text-text-2">{id.slice(0, 8)}</span>
      </div>
      <nav aria-label="Mission screens" className="-mx-1 overflow-x-auto pb-1">
        <ul className="row list-none gap-1 px-1 p-0" style={{ flexWrap: "nowrap" }}>
          {SCREENS.map((s) => {
            const href = `/agent/${id}${s.seg ? `/${s.seg}` : ""}`;
            const active = currentSeg === s.seg;
            return (
              <li key={href} className="shrink-0">
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className="inline-flex rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                  style={
                    active
                      ? { background: "var(--color-accent)", color: "#fff" }
                      : {
                          background: "var(--color-surface)",
                          border: "1px solid var(--color-border)",
                          color: "var(--color-text-2)",
                        }
                  }
                >
                  {s.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      {children}
    </div>
  );
}
