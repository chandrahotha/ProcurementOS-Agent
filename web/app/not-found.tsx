import Link from "next/link";
import { Icon } from "@/components/icons";

export default function NotFound() {
  return (
    <main className="flex min-h-[50vh] items-center justify-center">
      <div className="card flex max-w-md flex-col items-center gap-3 py-10 text-center">
        <span
          className="flex h-12 w-12 items-center justify-center rounded-full"
          style={{ background: "var(--color-accent-soft)", color: "var(--color-accent)" }}
        >
          <Icon name="search" size={22} />
        </span>
        <div className="text-sm font-semibold">Not found</div>
        <div className="text-sm text-text-2">
          That screen or mission does not exist (or belongs to another tenant —
          same shape either way).
        </div>
        <Link
          href="/agent"
          className="primary mt-1"
          role="button"
        >
          Back to Mission Control
        </Link>
      </div>
    </main>
  );
}
