// P01 Mission Control, wired: token box + live mission table.
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Screen, ExceptionBanner } from "@/components/Screen";
import { CommandPalette } from "@/components/CommandPalette";
import { ApiError, api, type Mission } from "@/lib/api-client";
import { readToken, saveToken } from "@/lib/token";

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
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        setState("denied");
      } else {
        setState("error");
      }
      setErr(e instanceof Error ? e.message : "load failed");
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

  return (
    <Screen code="P01" title="Mission Control" breadcrumb="Mission Control"
      status="Live mission states" primary="New mission" state={state === "empty" ? "empty" : state === "loading" ? "loading" : state === "success" ? "success" : state}>
      <CommandPalette />
      {state === "empty" && !missions.length ? (
        <form onSubmit={(e) => {
          e.preventDefault();
          const v = (e.currentTarget.elements.namedItem("tok") as HTMLInputElement).value;
          connect(v.trim());
        }}>
          <label>Dev API token (demo only; OIDC in production)
            <input name="tok" defaultValue={token} placeholder="tok-…" />
          </label>
          <button type="submit">Connect</button>
        </form>
      ) : null}
      {err && state !== "success" ? <p role="alert">{err}</p> : null}
      {state === "success" ? (
        <>
          <ExceptionBanner count={missions.filter((m) => m.coverage_pct < 80).length}
            worst="low coverage" href="/agent" />
          <table>
            <thead>
              <tr><th>Title</th><th>State</th><th>Coverage</th><th>Dial</th></tr>
            </thead>
            <tbody>
              {missions.map((m) => (
                <tr key={m.id}>
                  <td><Link href={`/agent/${m.id}/evidence`}>{m.title}</Link></td>
                  <td>{m.state}</td>
                  <td>{m.coverage_pct}%</td>
                  <td>{m.autonomy_level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </Screen>
  );
}
