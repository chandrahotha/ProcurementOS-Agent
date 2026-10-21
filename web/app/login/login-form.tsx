// The sign-in form: an email and a password, exchanged for a session
// token. Production swaps this for the OIDC redirect; the server enforces
// every gate regardless of who is asking.
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui";
import { saveToken } from "@/lib/token";
import { Icon } from "@/components/icons";
import { api, ApiError } from "@/lib/api-client";

const PERSONAS = [
  { label: "Buyer", email: "amara.buyer1@syn.example", desc: "create missions, intake, drafts" },
  { label: "Manager", email: "daniel.manager@syn.example", desc: "plans, approvals, optimizer" },
  { label: "Finance", email: "fatima.finance@syn.example", desc: "finance lane decisions" },
  { label: "Compliance", email: "chen.compliance@syn.example", desc: "compliance lane, waivers" },
];

// The seeded demo password. It is synthetic, it is published in the
// runbook, and it authenticates nothing outside the local demo database.
const DEMO_PASSWORD = "syn-Demo-2026!";

export default function LoginForm({ next }: { next: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function signIn(withEmail: string, withPassword: string) {
    if (!withEmail.trim() || !withPassword) {
      setErr("Enter your email and password.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const res = await api.login({ email: withEmail.trim(), password: withPassword });
      saveToken(res.token);
      router.push(next);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not sign in. Try again.");
      setBusy(false);
    }
  }

  return (
    <Card>
      <form
        className="grid gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          void signIn(email, password);
        }}
      >
        <label>Email
          <input
            name="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </label>
        <label>Password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
        </label>
        {err ? (
          <p role="alert" className="mt-2 text-xs" style={{ color: "var(--color-danger)" }}>
            {err}
          </p>
        ) : null}
        <div className="row mt-3">
          <button type="submit" className="primary w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </form>
      <div className="my-4 flex items-center gap-3 text-[10px] uppercase tracking-widest text-text-2">
        <span className="h-px flex-1" style={{ background: "var(--color-border)" }} />
        or use a demo persona
        <span className="h-px flex-1" style={{ background: "var(--color-border)" }} />
      </div>
      <div className="grid gap-3">
        {PERSONAS.map((p) => (
          <button
            key={p.email}
            type="button"
            disabled={busy}
            onClick={() => {
              setEmail(p.email);
              setPassword(DEMO_PASSWORD);
              void signIn(p.email, DEMO_PASSWORD);
            }}
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
      <p className="mt-4 text-xs text-text-2">
        Every seeded persona shares the demo password
        <span className="mono"> syn-Demo-2026! </span>
        and can sign in with it directly. Roles come from workspace
        membership and are enforced server-side.
      </p>
    </Card>
  );
}
