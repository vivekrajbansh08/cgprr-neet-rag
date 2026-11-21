import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

// Screenshots show MCC figures: docs/screenshots/ is gitignored, never committed.
const SHOTS = path.resolve(import.meta.dirname, "../../../docs/screenshots");
mkdirSync(SHOTS, { recursive: true });

const Q = {
  answered:
    "In NEET-UG 2025 MCC counselling, what was the Round 1 closing rank for MBBS at AIIMS New Delhi under the Open Seat Quota, Open category?",
  clarify: "What was the Round 1 closing rank for MBBS at Kasturba Medical College, Open category?",
  refused: "What was the 2025 MBBS closing rank at Armed Forces Medical College (AFMC), Pune?",
  guarantee: "Will I surely get MBBS at AIIMS New Delhi with AIR 30?",
};

const LOCAL = new Set(["127.0.0.1", "localhost", "[::1]"]);

function track(page: Page) {
  const seen = { total: 0, external: [] as string[] };
  page.on("request", (r) => {
    seen.total++;
    const u = new URL(r.url());
    if (u.protocol === "data:" || u.protocol === "blob:") return;
    if (!LOCAL.has(u.hostname)) seen.external.push(r.url());
  });
  return seen;
}

async function askAndWait(page: Page, question: string) {
  await page.goto("/#/ask");
  await page.getByLabel("Your question").fill(question);
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByRole("region", { name: "Answer" })).toBeVisible({ timeout: 180_000 });
  await page.waitForTimeout(900); // let the fade-in settle before the screenshot
}

async function predictor(page: Page, v: { rank: string; category: string; quota: string; course: string; round: string; state?: string }) {
  await page.goto("/#/predictor");
  await expect(page.locator("#p-quota option").first()).toBeAttached({ timeout: 30_000 });
  await page.getByLabel("All India Rank (AIR)").fill(v.rank);
  await page.getByLabel("Category").selectOption(v.category);
  await page.getByLabel("Quota").selectOption(v.quota);
  await page.getByLabel("Course").selectOption(v.course);
  await page.getByLabel("Round").selectOption(v.round);
  await page.getByLabel("State (optional)").selectOption(v.state ?? "");
  await page.getByRole("button", { name: "Show options" }).click();
  await expect(page.getByRole("region", { name: "Predictor results" })).toBeVisible({ timeout: 180_000 });
  await page.waitForTimeout(900);
}

for (const width of [1440, 390]) {
  for (const scheme of ["light", "dark"] as const) {
    test(`flows ${width}px ${scheme}`, async ({ browser }) => {
      const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: scheme });
      const page = await ctx.newPage();
      const seen = track(page);
      const shot = async (name: string) => {
        // No horizontal page scroll, and no table scrolled or clipped sideways: every figure is in view.
        const overflow = await page.evaluate(() => ({
          page: document.documentElement.scrollWidth - window.innerWidth,
          clipped: [...document.querySelectorAll("table")]
            .filter((t) => t.offsetParent !== null)
            .filter((t) => t.parentElement!.scrollWidth > t.parentElement!.clientWidth + 1).length,
        }));
        expect(overflow, name).toEqual({ page: 0, clipped: 0 });
        await page.screenshot({ path: path.join(SHOTS, `${name}-${width}-${scheme}.png`), fullPage: true });
      };

      await page.goto("/#/ask");
      await expect(page.locator("html")).toHaveClass(scheme === "dark" ? /dark/ : /^(?!.*dark)/);

      await askAndWait(page, Q.answered);
      await expect(page.getByTestId("record")).toBeVisible();
      await expect(page.getByText("Checked against source").first()).toBeVisible();
      await shot("ask-answered");

      await askAndWait(page, Q.clarify);
      await expect(page.getByRole("group", { name: "Pick a campus" })).toBeVisible();
      await shot("ask-clarify");

      await askAndWait(page, Q.refused);
      await shot("ask-refused");

      await askAndWait(page, Q.guarantee);
      await expect(page.getByTestId("guarantee-note")).toBeVisible();
      await shot("ask-guarantee");

      await predictor(page, { rank: "3000", category: "OBC", quota: "Open Seat Quota", course: "MBBS", round: "1" });
      await expect(page.getByTestId("options")).toBeVisible();
      await shot("predictor-results");

      await predictor(page, { rank: "20000", category: "General", quota: "All India", course: "MBBS", round: "1", state: "Delhi (NCT)" });
      await shot("predictor-empty");

      await page.goto("/#/evidence");
      await expect(page.getByTestId("local-line")).toBeVisible();
      // The source table (a table when wide, stacked rows when narrow) shows each file's fingerprint
      // as a copy button with the full sha256 in its title.
      const fp = page.getByRole("button", { name: "Copy full sha256 fingerprint of Round 1 allotment result" }).filter({ visible: true });
      await expect(fp).toHaveText("95c607c2dbd7");
      await expect(fp).toHaveAttribute("title", /^95c607c2dbd7[0-9a-f]{52}$/);
      await expect(page.getByRole("heading", { name: "Evaluation" })).toBeVisible();
      await expect(page.getByTestId("blind-summary")).toBeVisible();
      await shot("evidence");

      console.log(`REQUESTS ${width}px ${scheme}: total=${seen.total} external=${seen.external.length}`);
      if (seen.external.length) console.log(seen.external.join("\n"));
      expect(seen.external).toEqual([]);
      await ctx.close();
    });
  }
}

test("keyboard focus is visible on the question input and send button", async ({ page }) => {
  await page.goto("/#/ask");
  const box = page.getByTestId("ask-box");
  const input = page.getByLabel("Your question");
  for (let i = 0; i < 15 && !(await input.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("Tab");
  await expect(input).toBeFocused();
  const boxOutline = await box.evaluate((el) => getComputedStyle(el));
  expect(boxOutline.outlineStyle).not.toBe("none");
  expect(parseFloat(boxOutline.outlineWidth)).toBeGreaterThanOrEqual(2);

  await page.keyboard.type("test");
  await page.keyboard.press("Tab");
  const send = page.getByRole("button", { name: "Send question" });
  await expect(send).toBeFocused();
  const s = await send.evaluate((el) => getComputedStyle(el));
  expect(s.outlineStyle).not.toBe("none");
  expect(parseFloat(s.outlineWidth)).toBeGreaterThanOrEqual(2);
  await page.screenshot({ path: path.join(SHOTS, "focus-send-1440-light.png") });
});

test("clarify pick sends institute_id; a new typed question never carries the old pin", async ({ page }) => {
  const bodies: Record<string, unknown>[] = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/answer/ask")) bodies.push(JSON.parse(r.postData() ?? "{}"));
  });
  await askAndWait(page, Q.clarify);
  const pick = page.getByRole("group", { name: "Pick a campus" }).getByRole("button").first();
  await pick.click();
  await expect(page.getByRole("region", { name: "Answer" })).toBeVisible({ timeout: 180_000 });
  await expect.poll(() => bodies.length).toBe(2);
  expect(typeof bodies[1].institute_id).toBe("number");
  await page.waitForFunction(() => !document.querySelector('[aria-busy="true"]'), undefined, { timeout: 180_000 });
  await page.getByLabel("Your question").fill(Q.answered);
  await page.getByRole("button", { name: "Send question" }).click();
  await expect.poll(() => bodies.length).toBe(3);
  expect(bodies[2]).toEqual({ question: Q.answered });
});

test("predictor rank is validated client-side with a labelled inline message", async ({ page }) => {
  const posts: string[] = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/predictor/predict")) posts.push(r.url());
  });
  await page.goto("/#/predictor");
  await expect(page.locator("#p-quota option").first()).toBeAttached({ timeout: 30_000 });
  const rank = page.getByLabel("All India Rank (AIR)");
  await rank.fill("12,000");
  await page.getByRole("button", { name: "Show options" }).click();
  await expect(page.getByTestId("rank-error")).toHaveText(/digits only/);
  await expect(rank).toHaveAttribute("aria-invalid", "true");
  await expect(rank).toHaveAttribute("aria-describedby", "p-rank-msg");
  await expect(rank).toBeFocused();
  await rank.fill("0");
  await expect(page.getByTestId("rank-error")).toHaveText(/1 or more/);
  expect(posts).toEqual([]);
  await page.screenshot({ path: path.join(SHOTS, "predictor-rank-error-1440-light.png") });
});
