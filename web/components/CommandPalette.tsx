// Command palette (Cmd+K and "/" focus): navigate, jump between mission
// screens. Mounted globally in the root layout; the active mission id comes
// from the route (F3/F4/F5). Arrow keys + Enter, Escape, focus return (F55).
"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Icon } from "@/components/icons";

type Action = { group: string; label: string; href: string };

const STATIC_ACTIONS: Action[] = [
  { group: "Navigate", label: "Go: Mission Control", href: "/agent" },
  { group: "Navigate", label: "Go: New mission", href: "/agent/new" },
  { group: "Navigate", label: "Go: Dashboard", href: "/dashboard" },
  { group: "Navigate", label: "Go: Analytics", href: "/analytics" },
  { group: "Navigate", label: "Go: Suppliers", href: "/suppliers" },
  { group: "Navigate", label: "Go: Documents", href: "/documents" },
  { group: "Navigate", label: "Go: Reports", href: "/reports" },
  { group: "Navigate", label: "Go: Audit Log", href: "/audit" },
  { group: "Navigate", label: "Go: AI Runs", href: "/ai-runs" },
  { group: "Navigate", label: "Go: Workspaces", href: "/workspaces" },
  { group: "Navigate", label: "Go: Settings", href: "/settings" },
];

const MISSION_ACTIONS: Action[] = [
  { group: "Current mission", label: "Go: Evidence", href: "__mission__/evidence" },
  { group: "Current mission", label: "Go: Approval", href: "__mission__/approval" },
  { group: "Current mission", label: "Go: Action Center", href: "__mission__/actions" },
  { group: "Current mission", label: "Go: Task Board", href: "__mission__/tasks" },
  { group: "Current mission", label: "Go: Scenarios", href: "__mission__/scenarios" },
  { group: "Current mission", label: "Go: Decision Brief", href: "__mission__/decision" },
  { group: "Current mission", label: "Go: Mission Report", href: "__mission__/report" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const router = useRouter();
  const pathname = usePathname();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  // The active mission id: /agent/<id>/… but never /agent/new.
  const missionId =
    pathname?.match(/^\/agent\/([^/]+)/)?.[1] && pathname !== "/agent/new"
      ? pathname.match(/^\/agent\/([^/]+)/)![1]
      : undefined;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      // "/" opens the palette unless the user is typing in a field.
      if (
        e.key === "/" &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement) &&
        !(e.target instanceof HTMLSelectElement)
      ) {
        e.preventDefault();
        setOpen(true);
      }
      if (e.key === "Escape") setOpen(false);
    }
    function onOpen() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("pos-open-palette", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pos-open-palette", onOpen);
    };
  }, []);

  // Focus management: autofocus on open, restore to the invoking element on
  // close; simple focus trap while open (F55).
  useEffect(() => {
    if (open) {
      restoreRef.current = document.activeElement as HTMLElement | null;
      setQ("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    } else if (restoreRef.current) {
      restoreRef.current.focus();
      restoreRef.current = null;
    }
  }, [open]);

  if (!open) return null;

  const items = [...STATIC_ACTIONS, ...(missionId ? MISSION_ACTIONS : [])].filter(
    (a) =>
      a.label.toLowerCase().includes(q.toLowerCase()) ||
      a.group.toLowerCase().includes(q.toLowerCase()),
  );

  function go(href: string) {
    const url = missionId ? href.replace("__mission__", `/agent/${missionId}`) : href;
    if (url.includes("__mission__")) return;
    setOpen(false);
    router.push(url);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && items[active]) {
      e.preventDefault();
      go(items[active].href);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50"
      style={{ background: "rgb(15 23 42 / 0.4)" }}
      onClick={() => setOpen(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="palette"
        onKeyDown={onKeyDown}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="row mb-2 gap-2">
          <span style={{ color: "var(--color-text-2)" }}>
            <Icon name="search" size={14} />
          </span>
          <input
            ref={inputRef}
            autoFocus
            placeholder="Type a command…"
            value={q}
            aria-label="Search commands"
            aria-activedescendant={items[active] ? `cmd-${active}` : undefined}
            onChange={(e) => {
              setQ(e.target.value);
              setActive(0);
            }}
            className="flex-1 border-0 bg-transparent px-0 focus:outline-none"
            style={{ border: "none", outline: "none", boxShadow: "none" }}
          />
          <kbd className="mono rounded px-1.5 py-0.5 text-[10px]" style={{ background: "var(--color-surface-2)" }}>
            esc
          </kbd>
        </div>
        <ul ref={listRef}>
          {items.map((a, i) => (
            <li key={a.href} id={`cmd-${i}`} role="option" aria-selected={i === active}>
              <button
                type="button"
                onClick={() => go(a.href)}
                className={i === active ? "font-semibold" : ""}
                style={i === active ? { background: "var(--color-accent-soft)" } : undefined}
              >
                <span className="badge badge-neutral mr-2">{a.group}</span>
                {a.label.replace("Go: ", "")}
              </button>
            </li>
          ))}
          {items.length === 0 ? (
            <li className="px-3 py-4 text-center text-sm text-text-2">No matching command.</li>
          ) : null}
        </ul>
      </div>
    </div>
  );
}
