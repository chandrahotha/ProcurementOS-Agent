import { expect, test, type Page } from "@playwright/test";

// Smoke: Mission Control renders with its connect form and palette hint.
// Full W1-W8 click-through lands once the demo tenant is seeded (issue 6).
//
// Both tests authenticate first. A signed-out deep link is redirected to
// /login by design (the client clears the token and navigates on a 401), so
// a page under test that is loaded without a token is only observable in a
// race: the assertion sometimes runs before the redirect and sometimes
// after it, and the suite flakes. The token here is a seeded dev token
// for the synthetic tenant; it is not a secret and authenticates nobody.
const BUYER = "amara.buyer1@syn.example";

async function connect(page: Page) {
  await page.goto("/agent");
  await page.evaluate((t) => localStorage.setItem("pos_token", t), `dev-${BUYER}`);
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
