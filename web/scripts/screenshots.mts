// Capture every mission screen for the README and the walkthrough.
//
//   npx --prefix web tsx scripts/screenshots.mts <mission-id> [out-dir]
//
// The mission id is optional: without it the script takes the first
// mission the demo buyer can see. The stack has to be running
// (`python scripts/demo.py`).

import { chromium } from "@playwright/test";

const MID = process.argv[2] ?? "";
const OUT = process.argv[3] ?? "docs/screenshots";

/** The mission screens, as a function of the mission id. */
const pages = (id: string): [string, string][] => [
  ["P01", "/agent"],
  ["P04", `/agent/${id}/plan`],
  ["P05", `/agent/${id}/tasks`],
  ["P06", `/agent/${id}/evidence`],
  ["P07", `/agent/${id}/suppliers`],
  ["P08", `/agent/${id}/cost`],
  ["P09", `/agent/${id}/risk`],
  ["P10", `/agent/${id}/scenarios`],
  ["P11", `/agent/${id}/negotiation`],
  ["P12", `/agent/${id}/decision`],
  ["P13", `/agent/${id}/approval`],
  ["P14", `/agent/${id}/actions`],
  ["P15", `/agent/${id}/runs`],
  ["P16", `/agent/${id}/report`],
];

/** The furthest-along mission, so the captured screens show the product
 *  rather than an empty state. Fetched from Node: a `page.evaluate` with a
 *  named function expression is transpiled into a `__name` helper that does
 *  not exist in the browser. */
async function richestMission(): Promise<string> {
  const res = await fetch("http://localhost:8000/api/v1/missions", {
    headers: { Authorization: "Bearer dev-amara.buyer1@syn.example" },
  });
  const body = await res.json();
  const missions = body?.data?.missions ?? [];
  if (missions.length === 0) return "";
  const order = [
    "report", "action", "approval", "negotiation",
    "scenarios", "analysis", "evidence", "plan", "intake",
  ];
  const rank = (s: string): number => {
    const i = order.indexOf(s);
    return i === -1 ? order.length : i;
  };
  return [...missions].sort((a: { state: string }, b: { state: string }) => rank(a.state) - rank(b.state))[0]?.id ?? "";
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

const errors: string[] = [];
page.on("console", (m) => {
  if (m.type() === "error") errors.push(`console: ${m.text().slice(0, 200)}`);
});
page.on("pageerror", (e) => errors.push(`pageerror: ${String(e).slice(0, 200)}`));

await page.goto("http://localhost:3000/agent");
await page.evaluate(() => localStorage.setItem("pos_token", "dev-amara.buyer1@syn.example"));

const mission = MID || await richestMission();
if (!mission) {
  console.error("no mission found — start the demo with: python scripts/demo.py");
  await browser.close();
  process.exit(1);
}
console.log(`capturing ${pages(mission).length} screens for mission ${mission}\n`);

for (const [code, path] of pages(mission)) {
  errors.length = 0;
  await page.goto(`http://localhost:3000${path}`);
  await page.waitForTimeout(1200);
  const screen = await page.locator("main[data-screen]").first();
  const dataScreen = await screen.getAttribute("data-screen");
  const dataState = await screen.getAttribute("data-state");
  const text = (await screen.innerText()).replace(/\s+/g, " ").slice(0, 150);
  console.log(`${code.padEnd(4)} ${String(dataScreen).padEnd(5)} ${String(dataState).padEnd(8)} ${text}`);
  if (errors.length) console.log(`      !! ${errors.join(" | ")}`);
  await page.screenshot({ path: `${OUT}/shot-${code}.png`, fullPage: true });
}

await browser.close();
