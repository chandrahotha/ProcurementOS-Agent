// App shell (Slice 15): sidebar navigation + topbar with search/theme/user.
// Persistent so no route is reachable only by typing its URL (F43).
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "@/components/icons";
import { api } from "@/lib/api-client";

type NavItem = { label: string; href: string; icon: IconName };
type NavGroup = { title: string; items: NavItem[] };

const NAV: NavGroup[] = [
  {
    title: "Mission",
    items: [
      { label: "Mission Control", href: "/agent", icon: "mission" },
      { label: "New Mission", href: "/agent/new", icon: "plus" },
      { label: "Dashboard", href: "/dashboard", icon: "dashboard" },
      { label: "Analytics", href: "/analytics", icon: "chart" },
    ],
  },
  {
    title: "Workspace",
    items: [
      { label: "Suppliers", href: "/suppliers", icon: "suppliers" },
      { label: "Documents", href: "/documents", icon: "document" },
      { label: "Reports", href: "/reports", icon: "document" },
      { label: "Workspaces", href: "/workspaces", icon: "suppliers" },
    ],
  },
  {
    title: "Trust",
    items: [
      { label: "Audit Log", href: "/audit", icon: "shield" },
      { label: "AI Runs", href: "/ai-runs", icon: "sparkles" },
      { label: "Notifications", href: "/notifications", icon: "bell" },
    ],
  },
  {
    title: "Settings",
    items: [
      { label: "Settings", href: "/settings", icon: "settings" },
      { label: "Rules & Policies", href: "/settings/rules", icon: "shield" },
    ],
  },
];

function Brand() {
  return (
    <Link href="/agent" className="flex items-center gap-2.5 px-2 py-1">
      <span
        aria-hidden="true"
        className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white"
        style={{
          background: "linear-gradient(135deg, var(--color-accent), var(--color-accent-2))",
          boxShadow: "0 2px 8px rgb(79 70 229 / 0.35)",
        }}
      >
        P
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-sm font-semibold tracking-tight">ProcurementOS</span>
        <span className="text-[10px] font-medium uppercase tracking-widest text-text-2">
          Agent
        </span>
      </span>
    </Link>
  );
}

function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);
  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      window.localStorage.setItem("pos_theme", next ? "dark" : "light");
    } catch {
      /* private mode: theme is session-only */
    }
  }
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="ghost"
    >
      <Icon name={dark ? "sun" : "moon"} size={16} />
    </button>
  );
}

function UserChip() {
  const [email, setEmail] = useState("");
  useEffect(() => {
    const t = window.localStorage.getItem("pos_token") ?? "";
    if (!t) return;
    // The session token is opaque, so the name comes from the API rather
    // than from the token's own text.
    void api
      .me(t)
      .then((me) => setEmail(me.email))
      .catch(() => setEmail(""));
  }, []);
  return email ? (
    <span
      className="hidden max-w-44 items-center gap-2 truncate rounded-full px-3 py-1.5 text-xs font-medium sm:inline-flex"
      style={{ background: "var(--color-surface-2)", color: "var(--color-text-2)" }}
      title={email}
    >
      <Icon name="lock" size={12} />
      <span className="truncate">{email}</span>
    </span>
  ) : (
    <Link
      href="/login"
      className="hidden rounded-lg px-3 py-1.5 text-xs font-semibold text-white sm:inline-flex"
      style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-accent-2))" }}
    >
      Sign in
    </Link>
  );
}

function openPalette() {
  window.dispatchEvent(new Event("pos-open-palette"));
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <div className="app-body">
      {/* Mobile overlay */}
      {open ? (
        <div
          aria-hidden="true"
          className="fixed inset-0 z-30 lg:hidden"
          style={{ background: "rgb(15 23 42 / 0.4)" }}
          onClick={() => setOpen(false)}
        />
      ) : null}

      {/* Sidebar */}
      <aside
        className={`fixed bottom-0 left-0 top-0 z-40 flex w-60 flex-col gap-1 overflow-y-auto px-3 py-4 transition-transform duration-200 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{ background: "var(--color-surface)", borderRight: "1px solid var(--color-border)" }}
      >
        <div className="mb-3 flex items-center justify-between">
          <Brand />
          <button
            type="button"
            className="ghost lg:hidden"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          >
            <Icon name="x" size={16} />
          </button>
        </div>
        <nav aria-label="Primary" className="flex flex-1 flex-col gap-4">
          {NAV.map((group) => (
            <div key={group.title}>
              <div className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-widest text-text-2">
                {group.title}
              </div>
              <ul className="grid list-none gap-0.5 p-0">
                {group.items.map((item) => {
                  const active =
                    pathname === item.href ||
                    (item.href !== "/agent" && pathname.startsWith(item.href + "/")) ||
                    (item.href === "/agent" && pathname.startsWith("/agent") && pathname !== "/agent/new");
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors"
                        style={
                          active
                            ? {
                                background: "var(--color-accent-soft)",
                                color: "var(--color-accent)",
                              }
                            : { color: "var(--color-text-2)" }
                        }
                      >
                        <Icon name={item.icon} size={15} />
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
        <div className="px-2 pt-2 text-[10px] text-text-2">
          v0.1.0 · approval-gated · audit-chained
        </div>
      </aside>

      {/* Content column */}
      <div className="flex min-h-screen flex-col lg:pl-60">
        <header
          className="sticky top-0 z-20 flex items-center gap-2 px-4 py-2.5 backdrop-blur sm:px-6"
          style={{
            background: "color-mix(in srgb, var(--color-bg) 82%, transparent)",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <button
            type="button"
            className="ghost lg:hidden"
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
          >
            <Icon name="menu" size={18} />
          </button>
          <button
            type="button"
            onClick={openPalette}
            className="flex w-full max-w-sm items-center gap-2 rounded-lg px-3 py-1.5 text-sm"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-2)",
            }}
            aria-label="Open command palette"
          >
            <Icon name="search" size={14} />
            <span className="flex-1 text-left">Search or jump to…</span>
            <kbd className="mono hidden rounded border px-1.5 py-0.5 text-[10px] sm:inline" style={{ borderColor: "var(--color-border)" }}>
              ⌘K
            </kbd>
          </button>
          <div className="ml-auto flex items-center gap-1.5">
            <Link href="/notifications" aria-label="Notifications" className="ghost">
              <Icon name="bell" size={16} />
            </Link>
            <ThemeToggle />
            <UserChip />
          </div>
        </header>
        <div className="main-content flex-1">{children}</div>
      </div>
    </div>
  );
}
