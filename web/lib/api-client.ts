// Typed API client for every 05 endpoint. Envelope unwrapped; request_id
// surfaced on errors. Token comes from localStorage (demo) — production
// uses the OIDC session cookie via the route handlers.
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export type ScreenState =
  | "loading"
  | "empty"
  | "partial"
  | "success"
  | "processing"
  | "error"
  | "denied"
  | "stale"
  | "ai-unavailable";

export class ApiError extends Error {
  status: number;
  code: string;
  requestId: string;
  details?: unknown;
  constructor(status: number, code: string, message: string, requestId: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

export function verdictTone(verdict: string): "ok" | "warn" | "bad" {
  if (verdict === "ALLOW") return "ok";
  if (verdict === "NEEDS-APPROVAL") return "warn";
  return "bad";
}

async function call<T>(path: string, init: RequestInit, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (init.headers) Object.assign(headers, init.headers as Record<string, string>);
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers, cache: "no-store" });
  const rid = res.headers.get("X-Request-ID") ?? "";
  const isFile = (res.headers.get("Content-Type") ?? "").includes("application/")
    && !res.headers.get("Content-Type")?.includes("json");
  if (isFile && res.ok) return (await res.arrayBuffer()) as unknown as T;
  const body = (await res.json()) as {
    data?: T;
    error?: { code: string; message: string; details?: unknown };
    request_id?: string;
  };
  if (!res.ok) {
    throw new ApiError(res.status, body.error?.code ?? "http_error",
      body.error?.message ?? `HTTP ${res.status}`, body.request_id ?? rid, body.error?.details);
  }
  return body.data as T;
}

const get = <T,>(path: string, token?: string, key?: string) =>
  call<T>(path, { method: "GET", headers: key ? { "Idempotency-Key": key } : {} }, token);
const post = <T,>(path: string, body: unknown, token?: string, key?: string) =>
  call<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: key ? { "Idempotency-Key": key } : {},
  }, token);
const patch = <T,>(path: string, body: unknown, token?: string) =>
  call<T>(path, { method: "PATCH", body: JSON.stringify(body) }, token);

export type Mission = {
  id: string; workspace_id: string; title: string; state: string;
  coverage_pct: number; autonomy_level: string; currency: string;
};

type ScenarioOut = {
  scenario_id: string; allocations: unknown[];
  objective_value: number; savings_vs_baseline: number; candidate: boolean;
};

export const api = {
  missions: (t?: string) => get<{ missions: Mission[] }>(`/missions`, t),
  mission: (id: string, t?: string) => get<Mission>(`/missions/${id}`, t),
  createMission: (b: Record<string, unknown>, t?: string) =>
    post<Mission>(`/missions`, b, t),
  advance: (id: string, b: Record<string, unknown>, t?: string) =>
    post<Mission>(`/missions/${id}/advance`, b, t),
  upload: async (id: string, file: File, t?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    const headers: Record<string, string> = {};
    if (t) headers["Authorization"] = `Bearer ${t}`;
    const res = await fetch(`${BASE}/missions/${id}/documents`, {
      method: "POST", body: fd, headers,
    });
    const body = await res.json();
    if (!res.ok) throw new ApiError(res.status, body.error?.code ?? "upload_failed",
      body.error?.message ?? "upload failed", body.request_id ?? "");
    return body.data as { id: string; filename: string; status: string; reason: string };
  },
  documents: (id: string, t?: string) =>
    get<{ documents: { id: string; filename: string; status: string }[] }>(
      `/missions/${id}/documents`, t),
  plan: (id: string, t?: string) =>
    get<{ version: number; status: string; dag_hash: string; taskspecs: unknown[]; acknowledged_by: string | null }>(
      `/missions/${id}/plans/current`, t),
  generatePlan: (id: string, t?: string) =>
    post<{ version: number; tasks: number }>(`/missions/${id}/plans`, {}, t),
  acknowledge: (id: string, v: number, t?: string) =>
    post(`/missions/${id}/plans/${v}/acknowledge`, {}, t),
  tasks: (id: string, t?: string) =>
    get<{ tasks: { key: string; title: string; tool: string; status: string; attempts: number; plan_version: number; evidence_refs: string[] }[] }>(
      `/missions/${id}/tasks`, t),
  evidence: (id: string, t?: string) =>
    get<{ spans: Span[] }>(`/missions/${id}/evidence`, t),
  recordSpans: (id: string, spans: Record<string, unknown>[], t?: string) =>
    post<{ spans: Span[] }>(`/missions/${id}/evidence/spans`, spans, t),
  correctSpan: (id: string, span: string, b: Record<string, unknown>, t?: string) =>
    patch(`/missions/${id}/evidence/${span}`, b, t),
  analyze: (id: string, b: Record<string, unknown>, t?: string, key?: string) =>
    post<{ run_id: string; replayed: boolean }>(`/missions/${id}/analyze`, b, t, key),
  sourcing: (id: string, t?: string) =>
    get<{ lines: { line_id: string; supplier_id: string; normalized_total_minor: number; rank: number; compliant: boolean; evidence_refs: string[] }[] }>(
      `/missions/${id}/results/sourcing`, t),
  cost: (id: string, t?: string) =>
    get<{ costs: { supplier_id: string; tco_minor: number; build_up: Record<string, number>; fx: unknown[]; stale: boolean }[] }>(
      `/missions/${id}/results/cost`, t),
  risk: (id: string, t?: string) =>
    get<{ risks: { supplier_id: string; dimensions: Record<string, number>; composite: number; band: string; weights_version: string }[] }>(
      `/missions/${id}/results/risk`, t),
  scenario: (id: string, b: Record<string, unknown>, t?: string) =>
    post<ScenarioOut>(`/missions/${id}/scenarios`, b, t),
  optimize: (id: string, b: Record<string, unknown>, t?: string) =>
    post<ScenarioOut>(`/missions/${id}/scenarios/optimize`, b, t),
  draft: (id: string, b: Record<string, unknown>, t?: string) =>
    post<{ supplier_id: string; sent: boolean; ladder: { opening: number; target: number; walk_away: number; concessions: number[] } }>(
      `/missions/${id}/negotiation/drafts`, b, t),
  brief: (id: string, t?: string) => get<{
    winner_supplier_id: string | null; winner_tco_minor: number | null;
    ranking: { supplier_id: string; tco_minor: number }[];
    candidate_scenarios: string[];
    exceptions: { stale_fx_suppliers: string[]; lines_ranked: number };
    evidence_note: string; cited_lines: string[];
  }>(`/missions/${id}/brief`, t),
  requestApprovals: (id: string, b: Record<string, unknown>, t?: string) =>
    post<{ approvals: { id: string; lane: string; status: string }[] }>(
      `/missions/${id}/approvals`, b, t),
  decide: (id: string, aid: string, b: Record<string, unknown>, t?: string) =>
    post<{ id: string; status: string; quorum_met: boolean }>(
      `/missions/${id}/approvals/${aid}/decide`, b, t),
  dryRun: (id: string, b: Record<string, unknown>, t?: string) =>
    post<{ verdict: string; policy: string; payload: unknown }>(
      `/missions/${id}/actions/dry-run`, b, t),
  execute: (id: string, b: Record<string, unknown>, t?: string, key?: string) =>
    post<{ receipt: Record<string, unknown>; replayed: boolean }>(
      `/missions/${id}/actions/execute`, b, t, key),
  runs: (id: string, t?: string) => get(`/missions/${id}/runs`, t),
  timeline: (id: string, t?: string) =>
    get<{ events: { kind: string; at: string; actor: string }[] }>(
      `/missions/${id}/timeline`, t),
  workspaces: (t?: string) =>
    get<{ workspaces: { id: string; name: string; budget_currency: string }[] }>(
      `/workspaces`, t),
  scenariosList: (id: string, t?: string) =>
    get<{ scenarios: { scenario_id: string; allocations: unknown[]; objective_value: number; candidate: boolean; savings_vs_baseline: number }[] }>(
      `/missions/${id}/scenarios`, t),
  approvalsList: (id: string, t?: string) =>
    get<{ approvals: { id: string; lane: string; status: string; action_class: string; expires_at: string | null; payload_hash: string }[] }>(
      `/missions/${id}/approvals`, t),
  retryTask: (id: string, key: string, t?: string, ik?: string) =>
    post(`/missions/${id}/tasks/${key}/retry`, {}, t, ik),
  reviewTask: (id: string, key: string, b: Record<string, unknown>, t?: string) =>
    post(`/missions/${id}/tasks/${key}/review`, b, t),
  settle: (id: string, t?: string) =>
    post(`/missions/${id}/actions/settle`, {}, t),
  replay: (id: string, rid: string, t?: string) =>
    post<{ verdict: string; tco_integrity: boolean }>(
      `/missions/${id}/runs/${rid}/replay`, {}, t),
  audit: (t?: string, limit?: number) =>
    get<{ events: { id: string; action: string; object_type: string; mission_id: string | null; actor_id: string | null; request_id: string; reason: string | null; event_hash: string; at: string }[] }>(
      `/audit${limit ? `?limit=${limit}` : ""}`, t),
  rules: (t?: string) =>
    get<{ rules: { version: string; effective_from: string; weights: Record<string, number>; tolerances: Record<string, number>; fx_policy: Record<string, unknown>; changelog: string }[] }>(
      `/rules`, t),
  exportFile: async (id: string, fmt: "CSV" | "XLSX" | "PDF", t?: string) => {
    const res = await fetch(`${BASE}/missions/${id}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}) },
      body: JSON.stringify({ format: fmt }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiError(res.status, body?.error?.code ?? "export_failed",
        body?.error?.message ?? `HTTP ${res.status}`, body?.request_id ?? "");
    }
    const disp = res.headers.get("Content-Disposition") ?? "";
    const name = disp.match(/filename=([^;]+)/)?.[1] ?? `report-${id}.${fmt.toLowerCase()}`;
    return { blob: await res.blob(), filename: name.replace(/"/g, "") };
  },
};

export type Span = {
  id: string; document_id: string; field_name: string; field_value: string;
  quoted_text: string; confidence: number; extractor_version: string;
  instruction_flag: boolean;
};
