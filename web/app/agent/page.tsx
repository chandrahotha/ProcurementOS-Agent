import { Screen, ExceptionBanner } from "@/components/Screen";

// P01 Mission Control: KPI row + mission table + timeline preview (06 §5).
export default function MissionControl() {
  return (
    <Screen
      code="P01"
      title="Mission Control"
      breadcrumb="Mission Control"
      status="Live mission states"
      primary="New mission"
    >
      <ExceptionBanner count={0} worst="" href="/agent" />
    </Screen>
  );
}
