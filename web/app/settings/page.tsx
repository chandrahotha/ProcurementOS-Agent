// G14 Settings, wired (F41): settings index with cards to the sub-pages.
"use client";

import Link from "next/link";
import { Screen } from "@/components/Screen";
import { Icon, type IconName } from "@/components/icons";

const CARDS: { title: string; desc: string; href: string; icon: IconName }[] = [
  {
    title: "Users & Roles",
    desc: "Membership, personas, and deny-by-default RBAC",
    href: "/settings/users",
    icon: "suppliers",
  },
  {
    title: "Rules & Policies",
    desc: "Rule versions, weights, tolerances — read-only, dual-controlled",
    href: "/settings/rules",
    icon: "shield",
  },
  {
    title: "Security & Privacy",
    desc: "Sessions, tokens, and data controls",
    href: "/settings/security",
    icon: "lock",
  },
  {
    title: "Integrations",
    desc: "OIDC, AI providers, queue, and storage wiring",
    href: "/settings/integrations",
    icon: "link",
  },
];

export default function SettingsPage() {
  return (
    <Screen code="G14" title="Settings" breadcrumb="Settings"
      status="Deny-by-default by contract — changes are dual-controlled server-side">
      <div className="grid gap-3 sm:grid-cols-2">
        {CARDS.map((c) => (
          <Link key={c.href} href={c.href} className="card row items-start gap-3 transition-shadow hover:shadow-[var(--shadow-lift)]">
            <span
              className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
              style={{ background: "var(--color-accent-soft)", color: "var(--color-accent)" }}
            >
              <Icon name={c.icon} size={16} />
            </span>
            <span className="grid">
              <span className="text-sm font-semibold">{c.title}</span>
              <span className="text-xs text-text-2">{c.desc}</span>
            </span>
          </Link>
        ))}
      </div>
    </Screen>
  );
}
