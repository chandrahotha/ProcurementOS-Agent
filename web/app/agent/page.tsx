// P01 Mission Control, wired: the live mission table + KPI summary.
// When there is no session (or the session has expired) the screen asks
// you to sign in rather than offering a token box (F15).
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { ApiError, api, stateForError, type Mission } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Card, Progress, StatCard, StateBadge } from "@/components/ui";

export default function MissionControl() {
  const [token, setToken] = useState("");
  const [missions, setMissions] = useState<Mission[]>([]);
  const [state, setState] = useState<"loading" | "success" | "error" | "denied" | "empty">("loading");
  const [err, setErr] = useState("");

  useEffect(() => {
    setToken(readToken());
  }, []);

  useEffect(() => {
    if (!token) {
      setState("empty");
      return;
    }
    // The fetch lives inside the effect so the effect has no dependency it
    // cannot satisfy, and so a response that arrives after the token has
    // changed cannot overwrite the newer screen's data (F16).
    let cancelled = false;
    void (async () => {
      try {
        const data = await api.missions(token);
        if (cancelled) return;
        setMissions(data.missions);
        setState(data.missions.length ? "success" : "empty");
      } catch (e) {
        if (cancelled) return;
        setState(stateForError(e));
        setErr(e instanceof ApiError ? e.message : "load failed");
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const connectCard = (
    <Card className="max-w-lg">
      <div className="grid gap-3">
        <p className="text-sm text-text-2">
          You are not signed in, or your session has expired. Sign in with
          your email and password to see the missions you belong to.
        </p>
        <div className="row">
          <Link href="/login" className="primary">Sign in</Link>
        </div>
      </div>
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
