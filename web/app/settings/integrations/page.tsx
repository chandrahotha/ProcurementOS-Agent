// G18 Integrations (F42): the wiring this product owns — OIDC, AI providers,
// queue, storage. Read-only posture; credentials rotate dual-controlled.
"use client";

import { Screen } from "@/components/Screen";
import { Card, StateBadge } from "@/components/ui";
import { Icon } from "@/components/icons";

const INTEGRATIONS = [
  {
    name: "OIDC Identity",
    desc: "RS256/JWKS validation; dev-token fallback fenced off",
    icon: "lock" as const,
    status: "wired",
  },
  {
    name: "AI Providers",
    desc: "Primary + fallback with a persistent circuit breaker",
    icon: "sparkles" as const,
    status: "wired",
  },
  {
    name: "Queue (RQ)",
    desc: "pos:* namespace, retry/backoff, poison quarantine",
    icon: "play" as const,
    status: "wired",
  },
  {
    name: "Object Storage (S3)",
    desc: "Immutable DocumentVersions with SHA-256",
    icon: "document" as const,
    status: "wired",
  },
];

export default function IntegrationsPage() {
  return (
    <Screen code="G18" title="Integrations" breadcrumb={[{ label: "Settings", href: "/settings" }, { label: "Integrations" }]}
      status="Own DB, schema, queue namespaces, and buckets — zero sibling calls">
      <div className="grid gap-3 sm:grid-cols-2">
        {INTEGRATIONS.map((i) => (
          <div key={i.name} className="card row items-start gap-3">
            <span
              className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
              style={{ background: "var(--color-accent-soft)", color: "var(--color-accent)" }}
            >
              <Icon name={i.icon} size={16} />
            </span>
            <span className="grid flex-1">
              <span className="row items-center gap-2">
                <span className="text-sm font-semibold">{i.name}</span>
                <StateBadge state="active" />
              </span>
              <span className="mt-0.5 text-xs text-text-2">{i.desc}</span>
            </span>
          </div>
        ))}
      </div>
      <p className="max-w-xl text-xs text-text-2">
        Credential rotation is dual-controlled (audited, expiry-bound); it is
        never applied from this screen. Configure via environment only —
        see <span className="mono">.env.example</span>.
      </p>
    </Screen>
  );
}
