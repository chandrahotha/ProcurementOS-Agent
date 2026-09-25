// P05 Task Board, wired: status board with retry (idempotent) and review.
"use client";

import { use, useEffect, useState } from "react";
import { Screen } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

type Task = { key: string; title: string; tool: string; status: string;
  attempts: number; evidence_refs: string[] };

const COLUMNS = ["queued", "running", "needs_review", "blocked", "done"];

export default function TasksPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"loading" | "success" | "empty">("loading");

  async function load() {
    try {
      const d = await api.tasks(id, readToken());
      setTasks(d.tasks);
      setState(d.tasks.length ? "success" : "empty");
    } catch { setState("empty"); }
  }

  useEffect(() => { void load(); /* eslint-disable-next-line */ }, [id]);

  async function retry(key: string) {
    try {
      await api.retryTask(id, key, readToken(), `web-${key}-${Date.now()}`);
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
    <Screen code="P05" title="Task Board" breadcrumb="Mission / Tasks"
      primary="Retry task" state={state}>
      {state === "empty" ? <p>No tasks — generate and acknowledge a plan first.</p> : (
        <div className="board">
          {COLUMNS.map((col) => (
            <section key={col} className="col">
              <h2>{col}</h2>
              <ul>
                {tasks.filter((t) => t.status === col).map((t) => (
                  <li key={t.key} className="card">
                    <strong>{t.key}</strong>
                    <span className="mono">{t.tool}</span>
                    <div className="row">
                      {col !== "done" ? (
                        <button type="button" onClick={() => void retry(t.key)}>Retry</button>
                      ) : null}
                      <button type="button" onClick={() => void review(t.key, "accept")}>Accept</button>
                      <button type="button" onClick={() => void review(t.key, "flag")}>Flag</button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
      {note ? <p role="status">{note}</p> : null}
    </Screen>
  );
}
