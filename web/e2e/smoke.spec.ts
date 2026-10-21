import { expect, test, type Page } from "@playwright/test";

// Smoke: Mission Control renders and the palette hint works.
// Full W1-W8 click-through lands once the demo tenant is seeded (issue 6).
//
// Both tests sign in first, through the real login form. A signed-out deep
// link is redirected to /login by design (the client clears the token and
// navigates on a 401), so a page under test that is loaded without a
// session is only observable in a race: the assertion sometimes runs
// before the redirect and sometimes after it, and the suite flakes. The
// credentials are the seeded demo persona; the password is synthetic and
// published in the runbook.
const BUYER = "amara.buyer1@syn.example";
const DEMO_PASSWORD = "syn-Demo-2026!";

async function connect(page: Page) {
  await page.goto("/login");
  await page.fill('input[name="email"]', BUYER);
  await page.fill('input[name="password"]', DEMO_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/agent/);
}

test("P01 mission control loads", async ({ page }) => {
  await connect(page);
  await page.goto("/agent");
  await expect(page.getByRole("heading", { name: "Mission Control" })).toBeVisible();
  await expect(page.locator("main[data-screen='P01']")).toBeVisible();
});

test("approval gate renders mobile-first", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await connect(page);
  await page.goto("/agent/demo-mission/approval");
  await expect(page.getByRole("heading", { name: "Human Approval" })).toBeVisible();
  // Scoped to the header: when a real approval is pending, its card
  // renders a second Approve button, and the unscoped locator would then
  // match two elements and trip Playwright's strict mode (F26).
  await expect(
    page.locator("header").getByRole("button", { name: "Approve" }),
  ).toBeVisible();
});
