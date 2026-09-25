// G01 Login, wired (F28): dev-token connect with persona quick-select and a
// ?next= redirect back to the original route. Production swaps this for the
// OIDC redirect; the server enforces every gate regardless.
"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui";
import { saveToken } from "@/lib/token";
import { Icon } from "@/components/icons";

const PERSONAS = [
  { label: "Buyer", email: "amara.buyer1@syn.example", desc: "create missions, intake, drafts" },
  { label: "Manager", email: "daniel.manager@syn.example", desc: "plans, approvals, optimizer" },
  { label: "Finance", email: "fatima.finance@syn.example", desc: "finance lane decisions" },
  { label: "Compliance", email: "chen.compliance@syn.example", desc: "compliance lane, waivers" },
];

export default function LoginPage() {
  return (
    <Suspense fallback={<main data-screen="G01" aria-busy="true" className="grid min-h-[60vh] place-items-center"><div className="skeleton h-64 w-full max-w-md" /></main>}>
      <LoginInner />
    </Suspense>
  );
}

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") ?? "/agent";
  const [err, setErr] = useState("");

  function connect(token: string) {
    if (!token.trim()) {
      setErr("A token is required.");
      return;
    }
    saveToken(token.trim());
    router.push(next);
  }

  return (
    <main data-screen="G01" className="flex min-h-[60vh] items-center justify-center">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <span
            aria-hidden="true"
            className="flex h-12 w-12 items-center justify-center rounded-xl text-lg font-bold text-white"
            style={{
              background: "linear-gradient(135deg, var(--color-accent), var(--color-accent-2))",
              boxShadow: "0 4px 16px rgb(79 70 229 / 0.4)",
            }}
          >
            P
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
            <p className="mt-1 text-sm text-text-2">
              Autonomous procurement missions with approval gates.
            </p>
          </div>
        </div>
        <Card>
          <div className="grid gap-3">
            {PERSONAS.map((p) => (
              <button
                key={p.email}
                type="button"
                onClick={() => connect(`dev-${p.email}`)}
                className="row w-full justify-between px-3.5 py-2.5 text-left"
              >
                <span className="grid">
                  <span className="text-sm font-semibold">{p.label}</span>
                  <span className="text-xs text-text-2">{p.desc}</span>
                </span>
                <span style={{ color: "var(--color-accent)" }}>
                  <Icon name="link" size={15} />
                </span>
              </button>
            ))}
          </div>
          <div className="my-4 flex items-center gap-3 text-[10px] uppercase tracking-widest text-text-2">
            <span className="h-px flex-1" style={{ background: "var(--color-border)" }} />
            or paste a token
            <span className="h-px flex-1" style={{ background: "var(--color-border)" }} />
          </div>
          <form onSubmit={(e) => {
            e.preventDefault();
            const v = (e.currentTarget.elements.namedItem("tok") as HTMLInputElement).value;
            connect(v);
          }}>
            <label>API token
              <input name="tok" placeholder="tok-…" autoComplete="off" />
            </label>
            {err ? (
              <p role="alert" className="mt-2 text-xs" style={{ color: "var(--color-danger)" }}>
                {err}
              </p>
            ) : null}
            <div className="row mt-3">
              <button type="submit" className="primary w-full">Continue</button>
            </div>
          </form>
          <p className="mt-4 text-xs text-text-2">
            Dev tokens are a dev/test fallback only — unreachable once
            <span className="mono"> OIDC_ISSUER </span>is configured. Roles map by persona;
            membership is enforced server-side.
          </p>
        </Card>
      </div>
    </main>
  );
}
