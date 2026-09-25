// G17 AI Run History, wired (B48): tenant-wide AI jobs from GET /ai-jobs.
"use client";

import { useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api, stateForError } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";

type Job = { id: string; mission_id: string; purpose: string; provider: string;
  model_version: string; status: string; error: string | null; result_label: string | null; at: string };

export default function AIRunsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [state, setState] = useState<"loading" | "empty" | "success" | "denied">("loading");

  useEffect(() => {
    api.aiJobs(readToken())
      .then((d) => {
        setJobs(d.jobs);
        setState(d.jobs.length ? "success" : "empty");
      })
      .catch((e) => setState(stateForError(e) === "denied" ? "denied" : "empty"));
  }, []);

  const failed = jobs.filter((j) => j.status === "failed");

  return (
    <Screen code="G17" title="AI Run History" breadcrumb={[{ label: "Trust" }, { label: "AI Runs" }]}
      status="Provider, model version, and status per job — AI explains and drafts only" state={state}>
      {jobs.length === 0 ? (
        <EmptyState icon="sparkles" title="No AI jobs yet"
          body="AI jobs queue with retry and idempotency during outages; deterministic math is never affected."
          action={{ label: "Go to Mission Control", href: "/agent" }} />
      ) : (
        <div className="table-card">
          <table>
            <caption className="sr-only">AI jobs with provider and status</caption>
            <thead>
              <tr><th scope="col">At</th><th scope="col">Purpose</th><th scope="col">Provider</th><th scope="col">Model</th><th scope="col">Status</th><th scope="col">Mission</th></tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td data-label="At" className="mono">{j.at.slice(0, 19)}</td>
                  <td data-label="Purpose">{j.purpose}</td>
                  <td data-label="Provider" className="mono">{j.provider}</td>
                  <td data-label="Model" className="mono">{j.model_version}</td>
                  <td data-label="Status">
                    <StateBadge state={j.status === "failed" ? "failed" : j.status === "ok" ? "ok" : "pending"} />
                    {failed.length > 0 && j.error ? (
                      <span className="ml-2 text-xs text-text-2">{j.error}</span>
                    ) : null}
                  </td>
                  <td data-label="Mission" className="mono">{j.mission_id.slice(0, 8)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Screen>
  );
}
