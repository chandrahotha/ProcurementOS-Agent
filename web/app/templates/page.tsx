// TPL Mission Templates (F40): P02 is template-less by design (60-second
// creation); templates land here when the backend resource exists.
"use client";

import { Screen } from "@/components/Screen";
import { EmptyState } from "@/components/ui";

export default function TemplatesPage() {
  return (
    <Screen code="TPL" title="Mission Templates" breadcrumb={[{ label: "Mission" }, { label: "Templates" }]}
      status="Template-less creation is the 60-second default">
      <EmptyState icon="plan" title="No templates yet"
        body="Missions are created template-less against the seeded workspace list. A template picker that pre-fills the create form lands when the backend resource exists."
        action={{ label: "Create a mission", href: "/agent/new" }} />
    </Screen>
  );
}
