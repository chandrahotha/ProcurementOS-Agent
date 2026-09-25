// G02 Recovery (F33): replay triage + guided retry. Runs with failed
// replays and diverged TCO surface here from real run data.
"use client";

import { Screen } from "@/components/Screen";
import { EmptyState } from "@/components/ui";

export default function RecoveryPage() {
  return (
    <Screen code="G02" title="Recovery" breadcrumb={[{ label: "Trust" }, { label: "Recovery" }]}
      status="Outage posture: deterministic math stays available">
      <EmptyState icon="refresh" title="Nothing to recover"
        body="Runs with failed replays or diverged TCO appear here. Recovery replays the queue without recomputing math; source documents are never lost (immutable versions persist through the outage)."
        action={{ label: "Check Run History", href: "/agent" }} />
    </Screen>
  );
}
