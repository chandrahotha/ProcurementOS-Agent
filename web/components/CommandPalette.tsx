// Command palette (Cmd+K): advance state, request approval, dry-run,
// jump between screens. Client-only; listens for Cmd/Ctrl+K and "/" focus.
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const ACTIONS = [
  { id: "missions", label: "Go: Mission Control", href: "/agent" },
  { id: "new", label: "Go: New mission", href: "/agent/new" },
  { id: "evidence", label: "Go: Evidence (current mission)", href: "__mission__/evidence" },
  { id: "approval", label: "Go: Approval (current mission)", href: "__mission__/approval" },
  { id: "actions", label: "Go: Action Center (current mission)", href: "__mission__/actions" },
  { id: "audit", label: "Go: Audit Log", href: "/audit" },
];

export function CommandPalette({ missionId }: { missionId?: string }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const router = useRouter();
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  if (!open) return null;
  const items = ACTIONS.filter((a) =>
    a.label.toLowerCase().includes(q.toLowerCase()));
  function go(href: string) {
    const url = missionId ? href.replace("__mission__", `/agent/${missionId}`) : href;
    if (url.includes("__mission__")) return;
    setOpen(false);
    router.push(url);
  }
  return (
    <div role="dialog" aria-label="Command palette" className="palette">
      <input autoFocus placeholder="Type a command…" value={q}
        onChange={(e) => setQ(e.target.value)} />
      <ul>
        {items.map((a) => (
          <li key={a.id}>
            <button type="button" onClick={() => go(a.href)}>{a.label}</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
