// P15 Run History, wired: runs table + sandbox replay (Manager).
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Run = { id: string; trigger: string; rule_version: string;
  status: string; inputs_hash: string };

export default function RunsPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [runs, setRuns] = useState<Run[]>([]);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"empty" | "success">("empty");

  useEffect(() => {
    api.runs(id, readToken())
      .then((d) => {
        const r = (d as { runs: Run[] }).runs ?? [];
        setRuns(r);
        setState(r.length > 0 ? "success" : "empty");
      })
      .catch(() => setState("empty"));
  }, [id]);

  async function replay(rid: string) {
    setNote("");
    try {
      const d = await api.replay(id, rid, readToken());
      setNote(`Replay verdict: ${d.verdict}. TCO integrity: ${d.tco_integrity ? "ok" : "diverged"}.`);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "replay failed");
    }
  }

  return (
    <Screen code="P15" title="Run History" breadcrumb="Mission / Runs"
      primary="Replay in sandbox" state={state}>
      {state === "empty" ? <p>No runs recorded yet.</p> : (
        <table>
          <thead>
            <tr><th>Run</th><th>Trigger</th><th>Rule</th><th>Status</th><th>Inputs hash</th><th></th></tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td className="mono">{r.id.slice(0, 8)}</td>
                <td>{r.trigger}</td>
                <td className="mono">{r.rule_version}</td>
                <td>{r.status}</td>
                <td className="mono">{r.inputs_hash.slice(0, 12)}…</td>
                <td><button type="button" onClick={() => void replay(r.id)}>Replay</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {note ? <p role="status">{note}</p> : null}
    </Screen>
  );
}
