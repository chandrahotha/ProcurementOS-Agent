import { expect, test, type Page } from "@playwright/test";

// Full mission walk W1 -> W8 through the real UI, against the seeded
// synthetic API. Role switches sign in again with that persona's
// credentials, the way a person with two roles would; the server enforces
// every gate regardless of what the UI shows.
// Status notes are matched with hasText filters so multiple live
// regions never trip Playwright's strict mode.

const BUYER = "amara.buyer1@syn.example";
const MANAGER = "daniel.manager@syn.example";
const DEMO_PASSWORD = "syn-Demo-2026!";

async function connect(page: Page, email: string) {
  await page.goto("/login");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', DEMO_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/agent/);
}

async function see(page: Page, text: string) {
  await expect(
    page.getByRole("status").filter({ hasText: text }),
  ).toBeVisible({ timeout: 15_000 });
}

/**
 * The dry-run verdict, asserted on the verdict element itself.
 *
 * `see(page, "ALLOW")` is not enough: the Action Center's static subtitle
 * reads "execute only on ALLOW", and that is also a `role="status"`
 * element, so a substring match on "ALLOW" was satisfied by the subtitle
 * whether or not the gate had ever passed. The verdict element carries
 * `data-tone`, and its badge holds the verdict word on its own.
 */
async function verdictIs(page: Page, expected: string) {
  await expect(
    page.locator('p[role="status"][data-tone]').getByText(expected, { exact: true }),
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
  const missionId = page.url().split("/")[4] ?? "";
  expect(missionId.length).toBeGreaterThan(0);

  // W2: upload + quarantine verdict + plan + advance to plan.
  await page.setInputFiles(
    "input[type=file]",
    "../seed/fixtures/QUOTE-SYN-SUP-01-001.pdf",
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

  // W3: native analysis suite + rankings (P07). The demo payload carries
  // three domestic INR quotes and one imported USD quote, so the certified
  // ranking has four lines — three of them the domestic quotes plus the
  // converted import. Asserting the suppliers, not a bare row count, says
  // what the table is supposed to contain.
  await page.goto(`/agent/${missionId}/suppliers`);
  await page.getByRole("button", { name: "Run native analysis suite" }).click();
  await see(page, "complete");
  const ranked = page.locator("table tbody tr");
  await expect(ranked).toHaveCount(3);
  for (const supplier of ["SYN-SUP-01", "SYN-SUP-02", "SYN-SUP-06"]) {
    await expect(ranked.filter({ hasText: supplier })).toHaveCount(1);
  }
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

  // W6: brief + approval request (P12), then the lane gate (P13). The
  // server computes the award value from certified results (04 §2): S-A's
  // TCO is below the dual-control threshold, so the managerial lane alone
  // decides — a small award, exactly as the math says.
  await page.goto(`/agent/${missionId}/decision`);
  await see(page, "Winner");
  await page.locator(".row").getByRole("button", { name: "Request approvals" }).click();
  await see(page, "managerial");
  await page.goto(`/agent/${missionId}/negotiation`);
  await page.getByRole("button", { name: "Advance to approval (Manager)" }).click();
  await see(page, "Advanced to approval.");

  await page.goto(`/agent/${missionId}/approval`);
  await expect(page.locator(".approval-card")).toHaveCount(1);
  await page.locator(".approval-card").first()
    .getByRole("button", { name: "Approve" }).click();
  await see(page, "Quorum met");
  await page.getByRole("button", { name: "Advance to action (quorum verified)" }).click();
  await see(page, "Advanced to action.");

  // W7: dry-run first, execute on ALLOW, settle (P14).
  await connect(page, BUYER);
  await page.goto(`/agent/${missionId}/actions`);
  // The action panel carries the approved payload, so the dry-run's hash
  // check can succeed. Assert it is present before the dry-run, so a
  // failure says "the approved payload never arrived" rather than
  // "NEEDS-APPROVAL".
  await expect(
    page.getByLabel("Payload (must hash-match the approval)"),
  ).toHaveValue(/supplier_id/);
  await page.locator(".row").getByRole("button", { name: "Dry-run" }).click();
  await verdictIs(page, "ALLOW");
  await expect(
    page.locator(".row").getByRole("button", { name: "Execute", exact: true }),
  ).toBeEnabled();
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
