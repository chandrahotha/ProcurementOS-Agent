// Typed API client (Phase 7 expands per 05 §2). Propagates request_id.
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export async function apiGet<T>(path: string, requestId?: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: requestId ? { "X-Request-ID": requestId } : {},
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  const body = (await res.json()) as { data: T };
  return body.data;
}
