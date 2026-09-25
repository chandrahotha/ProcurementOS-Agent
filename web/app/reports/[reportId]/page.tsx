// G12 Report Viewer: exports land in the audit trail; the stored artifact
// re-downloads from the mission's Report screen.
"use client";

import { useParams } from "next/navigation";
import { Screen } from "@/components/Screen";
import { EmptyState } from "@/components/ui";

export default function ReportViewerPage() {
  const params = useParams<{ reportId: string }>();
  const id = params.reportId;
  return (
    <Screen code="G12" title="Report Viewer"
      breadcrumb={[{ label: "Reports", href: "/reports" }, { label: id.slice(0, 8) }]}
      status="Manifest header + evidence appendix">
      <EmptyState icon="document" title="Report artifacts re-download per mission"
        body={`Export ${id.slice(0, 8)} is recorded in the audit trail with its manifest — re-download it from the mission's Report screen.`}
        action={{ label: "Open Reports", href: "/reports" }} />
    </Screen>
  );
}
