// P01 Mission Control, wired: token box + live mission table + KPI summary.
// The connect form also renders after 401/403 so a bad token can be
// replaced from the UI (F15).
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { ApiError, api, stateForError, type Mission } from "@/lib/api-client";
import { readToken, saveToken } from "@/lib/token";
import { Card, Progress, StatCard, StateBadge } from "@/components/ui";

export default function MissionControl() {
  const [token, setToken] = useState("");
  const [missions, setMissions] = useState<Mission[]>([]);
  const [state, setState] = useState<"loading" | "success" | "error" | "denied" | "empty">("loading");
  const [err, setErr] = useState("");

  useEffect(() => {
    setToken(readToken());
  }, []);

  async function load(t: string) {
    if (!t) {
      setState("empty");
      return;
    }
    setState("loading");
    try {
      const data = await api.missions(t);
      setMissions(data.missions);
      setState(data.missions.length ? "success" : "empty");
    } catch (e) {
      setState(stateForError(e));
      setErr(e instanceof ApiError ? e.message : "load failed");
    }
  }

  useEffect(() => {
    if (token) void load(token);
    else setState("empty");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function connect(t: string) {
    saveToken(t);
    setToken(t);
  }

  const connectCard = (
    <Card className="max-w-lg">
      <form onSubmit={(e) => {
        e.preventDefault();
        const v = (e.currentTarget.elements.namedItem("tok") as HTMLInputElement).value;
        connect(v.trim());
      }}>
        <label>API token
          <input name="tok" defaultValue={token} placeholder="tok-…" />
        </label>
        <p className="mt-2 text-xs text-text-2">
          Dev tokens are a dev/test fallback (e.g. <span className="mono">dev-amara.buyer1@syn.example</span>);
          production uses OIDC. Roles map by persona.
        </p>
        <div className="row mt-3">
          <button type="submit" className="primary">Connect</button>
        </div>
      </form>
    </Card>
  );

  const lowCoverage = missions.filter((m) => m.coverage_pct < 80).length;
  const active = missions.filter((m) => !["report"].includes(m.state)).length;

  return (
    <Screen code="P01" title="Mission Control" breadcrumb="Mission Control"
      status="Live mission states" primary="New mission" primaryHref="/agent/new" state={state}>
      {state === "empty" && !missions.length ? connectCard : null}
      {state === "denied" || state === "error" ? (
        <>
          <p role="alert" className="text-sm" style={{ color: "var(--color-danger)" }}>{err}</p>
          {connectCard}
        </>
      ) : null}
      {state === "success" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Missions" value={missions.length} icon="mission" />
            <StatCard label="Active" value={active} icon="play" sub="not yet in report" />
            <StatCard
              label="Low coverage"
              value={lowCoverage}
              icon="alert"
              tone={lowCoverage ? "warn" : "ok"}
              sub="below the 80% gate"
            />
            <StatCard
              label="Avg coverage"
              value={`${missions.length ? Math.round(missions.reduce((a, m) => a + m.coverage_pct, 0) / missions.length) : 0}%`}
              icon="chart"
            />
          </div>
          <ExceptionBanner count={lowCoverage}
            worst="low coverage" href="/agent" />
          <div className="table-card">
            <table>
              <caption className="sr-only">Missions with state, coverage, and autonomy</caption>
              <thead>
                <tr><th scope="col">Title</th><th scope="col">State</th><th scope="col">Coverage</th><th scope="col">Dial</th></tr>
              </thead>
              <tbody>
                {missions.map((m) => (
                  <tr key={m.id}>
                    <td data-label="Title">
                      <Link href={`/agent/${m.id}`} className="font-medium hover:text-accent">
                        {m.title}
                      </Link>
                    </td>
                    <td data-label="State"><StateBadge state={m.state} /></td>
                    <td data-label="Coverage">
                      <span className="row gap-2">
                        <span className="mono">{m.coverage_pct}%</span>
                        <Progress pct={m.coverage_pct} tone={m.coverage_pct >= 80 ? "ok" : "warn"} />
                      </span>
                    </td>
                    <td data-label="Dial"><StateBadge state={m.autonomy_level} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </Screen>
  );
}
