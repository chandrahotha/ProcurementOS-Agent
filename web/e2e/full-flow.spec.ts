import { expect, test, type Page } from "@playwright/test";

// Full mission walk W1 -> W8 through the real UI, against the seeded
// synthetic API. Role switches use the dev tokens from the seed; the
// server enforces every gate regardless of what the UI shows.
// Status notes are matched with hasText filters so multiple live
// regions never trip Playwright's strict mode.

const BUYER = "amara.buyer1@syn.example";
const MANAGER = "daniel.manager@syn.example";
const FINANCE = "fatima.finance@syn.example";

async function connect(page: Page, email: string) {
  await page.goto("/agent");
  await page.evaluate(
    (t) => localStorage.setItem("pos_token", t),
    `dev-${email}`,
  );
  await page.reload();
}

async function see(page: Page, text: string) {
  await expect(
    page.getByRole("status").filter({ hasText: text }),
  ).toBeVisible({ timeout: 15_000 });
}

test("W1-W8: intake through report", async ({ page }) => {
  test.setTimeout(120_000);
  // W1: connect + create mission (P01 -> P02 -> P03).
  await connect(page, BUYER);
  await page.goto("/agent/new");
  await page.getByLabel("Title").fill(`E2E Mission ${Date.now()}`);
  await page.locator(".gate-grid").getByRole("button", { name: "Create mission" }).click();
  await page.waitForURL("**/agent/*/intake");
  const missionId = page.url().split("/")[4];
  expect(missionId.length).toBeGreaterThan(0);

  // W2: upload + quarantine verdict + plan + advance to plan.
  await page.setInputFiles(
    "input[type=file]",
    "../seed/fixtures/QUOTE-ACME-001.pdf",
  );
  await see(page, "clean");
  await page.locator(".row").getByRole("button", { name: "Generate plan" }).click();
  await see(page, "tasks");
  await page.getByRole("button", { name: "Advance to plan" }).click();
  await see(page, "Advanced to plan.");

  // Plan ack needs the manager (P04).
  await connect(page, MANAGER);
  await page.goto(`/agent/${missionId}/plan`);
  await see(page, "Version 1");
  await page.locator(".row").getByRole("button", { name: "Acknowledge plan" }).click();
  await see(page, "Plan v1 acknowledged.");
  await page.getByRole("button", { name: "Advance to evidence" }).click();
  await see(page, "Advanced to evidence.");

  // W2 evidence: quick-fill spans, coverage gate opens analysis (P06).
  await page.goto(`/agent/${missionId}/evidence`);
  await page.getByRole("button", { name: "Quick-fill 8 required fields" }).click();
  await see(page, "8 spans recorded");
  await page.getByRole("button", { name: "Advance to analysis" }).click();
  await see(page, "Advanced to analysis.");

  // W3: native analysis suite + rankings (P07).
  await page.goto(`/agent/${missionId}/suppliers`);
  await page.getByRole("button", { name: "Run native analysis suite" }).click();
  await see(page, "complete");
  await expect(page.locator("table tbody tr")).toHaveCount(2);
  await page.getByRole("button", { name: "Advance to scenarios" }).click();
  await see(page, "Advanced to scenarios.");

  // W4: candidate scenario + advance to negotiation (Manager, P10).
  await page.goto(`/agent/${missionId}/scenarios`);
  await page.getByRole("button", { name: "Create manual scenario" }).click();
  await see(page, "objective");
  await page.getByRole("button", { name: "Advance to negotiation (Manager)" }).click();
  await see(page, "Advanced to negotiation.");

  // W5: draft inside the ladder, no send (P11).
  await page.goto(`/agent/${missionId}/negotiation`);
  await page.getByRole("button", { name: "Draft inside ladder" }).click();
  await see(page, "Draft stored");
  await expect(page.locator("table tbody tr td").first()).toBeVisible();

  // W6: brief + approval request (P12), then the two-lane gate (P13).
  await page.goto(`/agent/${missionId}/decision`);
  await see(page, "Winner");
  await page.locator(".row").getByRole("button", { name: "Request approvals" }).click();
  await see(page, "managerial + finance");
  await page.goto(`/agent/${missionId}/negotiation`);
  await page.getByRole("button", { name: "Advance to approval (Manager)" }).click();
  await see(page, "Advanced to approval.");

  await page.goto(`/agent/${missionId}/approval`);
  await expect(page.locator(".approval-card")).toHaveCount(2);
  await page.locator(".approval-card").first()
    .getByRole("button", { name: "Approve" }).click();
  await see(page, "Recorded");

  await connect(page, FINANCE);
  await page.goto(`/agent/${missionId}/approval`);
  await page.locator(".approval-card").last()
    .getByRole("button", { name: "Approve" }).click();
  await see(page, "Quorum met");

  // Lanes decided; a Writer (Manager) carries the quorum forward.
  await connect(page, MANAGER);
  await page.goto(`/agent/${missionId}/approval`);
  await page.getByRole("button", { name: "Advance to action (quorum verified)" }).click();
  await see(page, "Advanced to action.");

  // W7: dry-run first, execute on ALLOW, settle (P14).
  await connect(page, BUYER);
  await page.goto(`/agent/${missionId}/actions`);
  await page.locator(".row").getByRole("button", { name: "Dry-run" }).click();
  await see(page, "ALLOW");
  await page.locator(".row").getByRole("button", { name: "Execute", exact: true }).click();
  await see(page, "Executed.");
  await page.locator(".row").getByRole("button", { name: "Mark actions settled" }).click();
  await see(page, "settled");
  await page.getByRole("button", { name: "Advance to report" }).click();
  await see(page, "Advanced to report.");

  // W8: export with evidence appendix (P16).
  await page.goto(`/agent/${missionId}/report`);
  await page.locator(".gate-grid").getByRole("button", { name: "Export", exact: true }).click();
  await see(page, "Exported");

  // G13: the audit trail carries the whole walk.
  await page.goto("/audit");
  await expect(page.locator("table tbody tr").first()).toBeVisible();
  await expect(page.locator("table")).toContainText("mission.state_changed");
});
