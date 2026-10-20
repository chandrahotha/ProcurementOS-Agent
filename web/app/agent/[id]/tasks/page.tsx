// P05 Task Board, wired: status board with retry (idempotent) and review.
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { EmptyState, StateBadge } from "@/components/ui";

type Task = { key: string; title: string; tool: string; status: string;
  attempts: number; plan_version: number; evidence_refs: string[] };

const COLUMNS = ["queued", "running", "needs_review", "blocked", "done"];

/** The task board for a mission. Module level so the effect and the
 *  reload-after-retry path share one implementation. */
async function fetchTasks(id: string): Promise<Task[]> {
  const d = await api.tasks(id, readToken());
  return d.tasks;
}

export default function TasksPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"loading" | "success" | "empty">("loading");

  async function load() {
    try {
      const list = await fetchTasks(id);
      setTasks(list);
      setState(list.length ? "success" : "empty");
    } catch { setState("empty"); }
  }

  // The fetch lives inside the effect so the effect has no dependency it
  // cannot satisfy, and so a response that arrives after the screen has
  // moved on cannot overwrite the newer screen's data (F16).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await fetchTasks(id);
        if (cancelled) return;
        setTasks(list);
        setState(list.length ? "success" : "empty");
      } catch { if (!cancelled) setState("empty"); }
    })();
    return () => { cancelled = true; };
  }, [id]);

  async function retry(key: string) {
    try {
      // Stable key per task (F13): double-clicks dedupe instead of
      // requeueing twice.
      await api.retryTask(id, key, readToken(), `web-${id}-${key}`);
      setNote(`${key} requeued.`);
      await load();
    } catch (e) { setNote(e instanceof Error ? e.message : "retry failed"); }
  }

  async function review(key: string, decision: "accept" | "flag") {
    try {
      await api.reviewTask(id, key, { decision }, readToken());
      setNote(`${key} reviewed: ${decision}.`);
      await load();
    } catch (e) { setNote(e instanceof Error ? e.message : "review failed"); }
  }

  return (
    <Screen code="P05" title="Task Board" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Tasks" }]}
      status={`${tasks.length} tasks across ${COLUMNS.length} lanes`} state={state}>
      {state === "empty" ? (
        <EmptyState icon="plan" title="No tasks"
          body="Generate and acknowledge a plan first — the board fills from the acknowledged plan version."
          action={{ label: "Go to Intake", href: `/agent/${id}/intake` }} />
      ) : (
        <div className="board">
          {COLUMNS.map((col) => (
            <section key={col} className="col">
              <h2>
                <StateBadge state={col} /> {col}
              </h2>
              <ul className="grid list-none gap-2 p-0">
                {tasks.filter((t) => t.status === col).map((t) => (
                  <li key={t.key} className="card">
                    <strong className="mono text-xs">{t.key}</strong>
                    <span className="text-xs text-text-2">{t.title || t.tool}</span>
                    <span className="mono text-[10px] text-text-2">
                      {t.tool} · v{t.plan_version} · {t.attempts} attempt{t.attempts === 1 ? "" : "s"}
                    </span>
                    <div className="row">
                      {col !== "done" ? (
                        <button type="button" className="ghost text-xs" onClick={() => void retry(t.key)}>Retry</button>
                      ) : null}
                      <button type="button" className="ghost text-xs" onClick={() => void review(t.key, "accept")}>Accept</button>
                      <button type="button" className="ghost text-xs" onClick={() => void review(t.key, "flag")}>Flag</button>
                    </div>
                  </li>
                ))}
                {tasks.filter((t) => t.status === col).length === 0 ? (
                  <li className="py-2 text-center text-[11px] text-text-2">—</li>
                ) : null}
              </ul>
            </section>
          ))}
        </div>
      )}
      {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
    </Screen>
  );
}
