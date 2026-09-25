"use client";

import { useEffect } from "react";
import { Icon } from "@/components/icons";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <main className="flex min-h-[50vh] items-center justify-center">
      <div className="card flex max-w-md flex-col items-center gap-3 py-10 text-center">
        <span
          className="flex h-12 w-12 items-center justify-center rounded-full"
          style={{ background: "var(--color-danger-soft)", color: "var(--color-danger)" }}
        >
          <Icon name="alert" size={22} />
        </span>
        <div className="text-sm font-semibold">Something went wrong</div>
        <div className="text-sm text-text-2">
          The screen failed to render. Retry safely — in-flight writes are never
          half-applied.
        </div>
        {error.digest ? (
          <div className="mono text-xs text-text-2">digest {error.digest}</div>
        ) : null}
        <button type="button" className="primary mt-1" onClick={reset}>
          Retry
        </button>
      </div>
    </main>
  );
}
