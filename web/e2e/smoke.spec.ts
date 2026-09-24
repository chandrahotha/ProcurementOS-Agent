import { expect, test } from "@playwright/test";

// Smoke: Mission Control renders with its connect form and palette hint.
// Full W1-W8 click-through lands once the demo tenant is seeded (issue 6).
test("P01 mission control loads", async ({ page }) => {
  await page.goto("/agent");
  await expect(page.getByRole("heading", { name: "Mission Control" })).toBeVisible();
  await expect(page.locator("main[data-screen='P01']")).toBeVisible();
});

test("approval gate renders mobile-first", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto("/agent/demo-mission/approval");
  await expect(page.getByRole("heading", { name: "Human Approval" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
});
