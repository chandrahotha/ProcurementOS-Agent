// Shared screen shell: header + breadcrumb + status + nine-state renderer.
// Every P-screen implements all nine states (06 add-on): loading, empty,
// partial, success, processing, error, denied, stale, AI-unavailable.
import React from "react";

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

export function Screen({
  code,
  title,
  breadcrumb,
  status,
  state = "success",
  primary,
  children,
}: {
  code: string;
  title: string;
  breadcrumb: string;
  status?: string;
  state?: ScreenState;
  primary?: string;
  children?: React.ReactNode;
}) {
  return (
    <main data-screen={code} data-state={state}>
      <nav aria-label="Breadcrumb">{breadcrumb}</nav>
      <header>
        <h1>{title}</h1>
        {status ? <p role="status">{status}</p> : null}
        {primary ? <button type="button">{primary}</button> : null}
      </header>
      {state === "loading" ? <div aria-busy="true">Loading…</div> : null}
      {state === "error" ? <div role="alert">Something went wrong. Retry safely.</div> : null}
      {state === "denied" ? <div role="alert">You do not have access.</div> : null}
      {state === "ai-unavailable" ? (
        <div role="note">AI unavailable — deterministic math unaffected.</div>
      ) : null}
      {children}
    </main>
  );
}

export function ExceptionBanner({ count, worst, href }: { count: number; worst: string; href: string }) {
  if (count === 0) return null;
  return (
    <div role="alert">
      {count} exceptions — worst: {worst} <a href={href}>Jump to item</a>
    </div>
  );
}
