// Shared screen shell: header + breadcrumb + status + nine-state renderer.
// Every P-screen implements all nine states (06 add-on): loading, empty,
// partial, success, processing, error, denied, stale, AI-unavailable.
import React from "react";
import Link from "next/link";
import { Icon } from "@/components/icons";
import { Skeleton } from "@/components/ui";

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

export type Crumb = { label: string; href?: string };

export function Screen({
  code,
  title,
  breadcrumb,
  status,
  state = "success",
  primary,
  primaryHref,
  onPrimary,
  children,
}: {
  code: string;
  title: string;
  breadcrumb: string | Crumb[];
  status?: string;
  state?: ScreenState;
  primary?: string;
  primaryHref?: string;
  onPrimary?: () => void;
  children?: React.ReactNode;
}) {
  const crumbs: Crumb[] =
    typeof breadcrumb === "string" ? [{ label: breadcrumb }] : breadcrumb;
  return (
    <main data-screen={code} data-state={state} className="grid gap-5">
      <nav aria-label="Breadcrumb">
        {/* NOTE: the `row` class is an e2e action-hook — structural
            containers must never use it. */}
        <ol className="flex list-none items-center gap-1.5 p-0 text-xs text-text-2">
          {crumbs.map((c, i) => (
            <li key={`${c.label}-${i}`} className="flex items-center gap-1.5">
              {i > 0 ? <span aria-hidden="true">/</span> : null}
              {c.href && i < crumbs.length - 1 ? (
                <Link href={c.href} className="hover:text-text">
                  {c.label}
                </Link>
              ) : (
                <span aria-current="page" className="font-medium">
                  {c.label}
                </span>
              )}
            </li>
          ))}
        </ol>
      </nav>
      <header className="flex items-start justify-between gap-3">
        <div className="grid gap-1">
          <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
          {status ? (
            <p role="status" className="text-sm text-text-2">
              {status}
            </p>
          ) : null}
        </div>
        {primary ? (
          primaryHref ? (
            <Link
              href={primaryHref}
              className="primary shrink-0"
              role="button"
              aria-label={primary}
            >
              {primary}
            </Link>
          ) : (
            <button type="button" className="primary shrink-0" onClick={onPrimary}>
              {primary}
            </button>
          )
        ) : null}
      </header>
      {state === "loading" ? (
        <div aria-busy="true" className="grid gap-3">
          <Skeleton className="h-9 w-64" />
          <div className="table-card">
            <Skeleton className="h-10 w-full rounded-none" />
            <Skeleton className="h-12 w-full rounded-none" />
            <Skeleton className="h-12 w-full rounded-none" />
            <Skeleton className="h-12 w-full rounded-none" />
          </div>
        </div>
      ) : null}
      {state === "processing" ? (
        <div
          role="status"
          className="row gap-2 rounded-lg p-3 text-sm"
          style={{ background: "var(--color-accent-soft)", color: "var(--color-accent)" }}
        >
          <span
            aria-hidden="true"
            className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
          />
          Processing…
        </div>
      ) : null}
      {state === "error" ? (
        <div
          role="alert"
          className="row gap-2 rounded-lg p-3 text-sm"
          style={{ background: "var(--color-danger-soft)", color: "var(--color-danger)" }}
        >
          <Icon name="alert" size={15} />
          Something went wrong. Retry safely.
        </div>
      ) : null}
      {state === "denied" ? (
        <div
          role="alert"
          className="row gap-2 rounded-lg p-3 text-sm"
          style={{ background: "var(--color-warn-soft)", color: "var(--color-warn)" }}
        >
          <Icon name="lock" size={15} />
          You do not have access.
        </div>
      ) : null}
      {state === "stale" ? (
        <div
          role="status"
          className="row gap-2 rounded-lg p-3 text-sm"
          style={{ background: "var(--color-warn-soft)", color: "var(--color-warn)" }}
        >
          <Icon name="clock" size={15} />
          Results are stale — re-run before deciding.
        </div>
      ) : null}
      {state === "ai-unavailable" ? (
        <div
          role="note"
          className="row gap-2 rounded-lg p-3 text-sm"
          style={{ background: "var(--color-surface-2)", color: "var(--color-text-2)" }}
        >
          <Icon name="sparkles" size={15} />
          AI unavailable — deterministic math unaffected.
        </div>
      ) : null}
      {state === "partial" ? (
        <div
          role="status"
          className="row gap-2 rounded-lg p-3 text-sm"
          style={{ background: "var(--color-warn-soft)", color: "var(--color-warn)" }}
        >
          <Icon name="alert" size={15} />
          Partial data — some sources are missing.
        </div>
      ) : null}
      {children}
    </main>
  );
}

export function ExceptionBanner({ count, worst, href }: { count: number; worst: string; href: string }) {
  if (count === 0) return null;
  return (
    <div
      role="alert"
      className="row gap-2 rounded-lg p-3 text-sm"
      style={{ background: "var(--color-danger-soft)", color: "var(--color-danger)" }}
    >
      <Icon name="alert" size={15} />
      {count} exception{count === 1 ? "" : "s"} — worst: {worst}
      <a href={href} className="underline underline-offset-2">
        Jump to item
      </a>
    </div>
  );
}
