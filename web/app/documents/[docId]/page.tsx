// G08 Document Viewer: the id refers to a mission-scoped document row; the
// real viewer renders from the mission's Intake queue.
"use client";

import { useParams } from "next/navigation";
import { Screen } from "@/components/Screen";
import { EmptyState } from "@/components/ui";

export default function DocumentViewerPage() {
  const params = useParams<{ docId: string }>();
  const id = params.docId;
  return (
    <Screen code="G08" title="Document Viewer"
      breadcrumb={[{ label: "Documents", href: "/documents" }, { label: id.slice(0, 8) }]}
      status="Immutable versions with SHA-256">
      <EmptyState icon="document" title="Document preview lands with the intake pipeline"
        body={`Document ${id.slice(0, 8)} is a mission-scoped row — open its mission's Intake screen for the quarantine verdict and extraction spans.`}
        action={{ label: "Open Documents Library", href: "/documents" }} />
    </Screen>
  );
}
