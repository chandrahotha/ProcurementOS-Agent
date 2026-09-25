import { defineConfig, devices } from "@playwright/test";

// Two servers: the API (sqlite-backed, seeded with SYNTHETIC data) and the
// web app. Both get torn down together; CI never reuses existing servers.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "python seed/seed_pos.py --tenant SYN-TENANT-01 " +
        "--db-url sqlite+aiosqlite:///./e2e_pos.db && " +
        "python -m uvicorn app.main:app --port 8000",
      cwd: "../",
      url: "http://localhost:8000/healthz",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        DATABASE_URL: "sqlite+aiosqlite:///./e2e_pos.db",
        WEB_ORIGIN: "http://localhost:3000",
      },
    },
    {
      command: "npm run start",
      url: "http://localhost:3000/agent",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
