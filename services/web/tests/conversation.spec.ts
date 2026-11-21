import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

// Conversational Ask view. Runs against the live local stack (answer :8002) through the Vite dev
// server. Expected figures are read from Postgres as neet_reader at test time; none are hard-coded.
// Screenshots show MCC figures: docs/screenshots/ is gitignored, never committed.
const ROOT = path.resolve(import.meta.dirname, "../../..");
const SHOTS = path.join(ROOT, "docs/screenshots");
mkdirSync(SHOTS, { recursive: true });

const Q = {
  jodhpur: "What was the closing rank for MBBS at AIIMS Jodhpur under Open Seat Quota, Open category?",
  followUp: "What was the Round 2 closing rank under Open Seat Quota, Open category?",
  kasturba: "What was the Round 1 closing rank for MBBS at Kasturba Medical College, Open category?",
};
const LLM = 180_000;

/** Read-only lookup as neet_reader (credentials from the repo's .env; never printed). */
function sql(query: string): string[][] {
  const env: Record<string, string> = {};
  for (const line of readFileSync(path.join(ROOT, ".env"), "utf8").split("\n")) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
  const out = execFileSync(
    "psql",
    ["-X", "-q", "-At", "-F", "\t", "-h", env.POSTGRES_HOST || "localhost", "-p", env.POSTGRES_HOST_PORT || "5432", "-U", "neet_reader", "-d", env.POSTGRES_DB || "neet", "-c", query],
    { env: { ...process.env, PGPASSWORD: env.NEET_READER_PASSWORD ?? "" }, encoding: "utf8" },
  );
  return out.trim().split("\n").filter(Boolean).map((l) => l.split("\t"));
}

/** AIIMS Jodhpur, MBBS, Open Seat Quota, Open, Round 2: institute id and closing rank text. */
function jodhpurRound2(): { id: number; rank: string; allotments: number } {
  const rows = sql(
    "SELECT c.institute_id, c.rank_text, c.allotments FROM neet.closing_rank c JOIN neet.institute i ON i.id = c.institute_id " +
      "WHERE i.display_name ILIKE 'AIIMS, Jodhpur%' AND c.round = 2 AND c.quota = 'Open Seat Quota' AND c.course = 'MBBS' AND c.allotted_category = 'Open'",
  );
  expect(rows, "exactly one DB cell for AIIMS Jodhpur R2 OSQ Open MBBS").toHaveLength(1);
  return { id: Number(rows[0][0]), rank: rows[0][1], allotments: Number(rows[0][2]) };
}

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
const external = { total: 0, external: 0 };
function report(name: string, seen: { total: number; external: string[] }) {
  external.total += seen.total;
  external.external += seen.external.length;
  console.log(`REQUESTS ${name}: total=${seen.total} external=${seen.external.length}`);
  expect(seen.external).toEqual([]);
}
test.afterAll(() => console.log(`REQUESTS conversation suite: total=${external.total} external=${external.external}`));

const answers = (page: Page) => page.getByRole("region", { name: "Answer" });
const idle = (page: Page) => page.waitForFunction(() => !document.querySelector('[aria-busy="true"]'), undefined, { timeout: LLM });

async function send(page: Page, question: string) {
  const before = await answers(page).count();
  const input = page.getByLabel("Your question");
  await input.fill(question);
  await input.press("Enter");
  await expect(answers(page)).toHaveCount(before + 1, { timeout: LLM });
  await idle(page);
}

/** Full-page capture with the window grown to the page height, so nothing is scrolled and sticky
 *  parts (side panel, pinned input) render where they sit in a tall window, not at the scroll offset. */
async function fullShot(page: Page, file: string) {
  const vp = page.viewportSize()!;
  await page.evaluate(() => window.scrollTo(0, 0));
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.setViewportSize({ width: vp.width, height: Math.max(vp.height, h) });
  await page.waitForTimeout(300);
  await page.screenshot({ path: file, fullPage: true });
  await page.setViewportSize(vp);
}

async function noHorizontalScroll(page: Page) {
  const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(over).toBe(0);
}

test("input is empty and focused after send", async ({ page }) => {
  const seen = track(page);
  await page.goto("/#/ask");
  const input = page.getByLabel("Your question");
  await input.fill(Q.jodhpur);
  await input.press("Enter");
  // Immediately: cleared, still focused, read-only while checking, placeholder row in the thread.
  await expect(input).toHaveValue("");
  await expect(input).toBeFocused();
  await expect(input).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByRole("status").filter({ hasText: "Checking against the source rows" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Checking against the source rows" })).toBeVisible();
  await expect(answers(page)).toHaveCount(1, { timeout: LLM });
  await idle(page);
  await expect(input).toHaveValue("");
  await expect(input).toBeFocused();
  await expect(input).not.toHaveAttribute("aria-disabled", "true");
  // Shift+Enter adds a line instead of sending.
  await input.pressSequentially("line one");
  await input.press("Shift+Enter");
  await input.pressSequentially("line two");
  await expect(input).toHaveValue("line one\nline two");
  await expect(answers(page)).toHaveCount(1);
  report("input-focus", seen);
});

for (const [width, scheme] of [[1440, "light"], [1440, "dark"], [390, "light"], [390, "dark"]] as const) {
  test(`two turns in order, chip follow-up answers AIIMS Jodhpur Round 2 from the DB (${width}px ${scheme})`, async ({ browser }) => {
    const expected = jodhpurRound2();
    const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: scheme });
    const page = await ctx.newPage();
    const seen = track(page);
    const bodies: Record<string, unknown>[] = [];
    page.on("request", (r) => {
      if (r.url().endsWith("/api/answer/ask")) bodies.push(JSON.parse(r.postData() ?? "{}"));
    });
    await page.goto("/#/ask");
    await expect(page.getByRole("heading", { name: "What would you like to check?" })).toBeVisible();

    await send(page, Q.jodhpur);
    await expect(page.getByRole("heading", { name: "What would you like to check?" })).toHaveCount(0);
    const chip = page.getByTestId("context-chip");
    await expect(chip).toContainText(/About: AIIMS, Jodhpur/);
    await expect(page.getByRole("button", { name: "Remove institute context" })).toBeVisible();

    await send(page, Q.followUp);
    expect(bodies.at(-1)).toEqual({ question: Q.followUp, institute_id: expected.id });

    // Both turns visible, in order, newest at the bottom.
    const qs = page.getByTestId("turn-question");
    await expect(qs).toHaveCount(2);
    await expect(qs.nth(0)).toContainText(Q.jodhpur);
    await expect(qs.nth(1)).toContainText(Q.followUp);
    const [y0, y1] = await Promise.all([qs.nth(0).boundingBox(), qs.nth(1).boundingBox()]);
    expect(y0!.y).toBeLessThan(y1!.y);

    // The follow-up answer is AIIMS Jodhpur, Round 2, with the figure in Postgres.
    const last = answers(page).last();
    const cards = last.getByTestId("record");
    await expect(cards).toHaveCount(1);
    await expect(cards).toContainText("Jodhpur");
    await expect(cards).toContainText(`Round 2 · from ${expected.allotments} allotment`);
    await expect(cards.locator(".font-serif")).toHaveText(expected.rank);
    // Fixed lead-in and credit lines are not in the rendered prose; the sources are a closed disclosure.
    await expect(last).not.toContainText("from the cited source rows:");
    await expect(last).not.toContainText("Source: Medical Counselling Committee");
    await expect(last.getByTestId("source-rows")).not.toHaveAttribute("open");
    await expect(page.locator("footer")).toContainText("Source: Medical Counselling Committee (MCC), Government of India, mcc.nic.in");

    // Input pinned and visible; no horizontal scroll.
    const input = page.getByLabel("Your question");
    await expect(input).toBeInViewport();
    await noHorizontalScroll(page);
    await expect(page.getByText("Conversation is not saved. Closing the tab clears it.")).toBeVisible();

    if (!(width === 390 && scheme === "dark")) {
      await page.waitForTimeout(900);
      await fullShot(page, path.join(SHOTS, `ask-thread-${width}-${scheme}.png`));
    }
    report(`thread ${width}px ${scheme}`, seen);
    await ctx.close();
  });
}

test("the same follow-up without the chip gives no AIIMS Jodhpur figure", async ({ page }) => {
  const seen = track(page);
  const bodies: Record<string, unknown>[] = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/answer/ask")) bodies.push(JSON.parse(r.postData() ?? "{}"));
  });
  await page.goto("/#/ask");
  await send(page, Q.jodhpur);
  await expect(page.getByTestId("context-chip")).toBeVisible();
  await page.getByRole("button", { name: "New conversation" }).click();
  await send(page, Q.followUp);
  expect(bodies.at(-1)).toEqual({ question: Q.followUp });
  const last = answers(page).last();
  await expect(last).not.toContainText("Jodhpur");
  await expect(last.getByTestId("record")).toHaveCount(0);
  report("no-chip follow-up", seen);
});

test("Kasturba clarify, then picking the Manipal campus answers for it and sets the chip", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const seen = track(page);
  const bodies: Record<string, unknown>[] = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/answer/ask")) bodies.push(JSON.parse(r.postData() ?? "{}"));
  });
  await page.goto("/#/ask");
  await send(page, Q.kasturba);
  const group = page.getByRole("group", { name: "Pick a campus" });
  await expect(group).toBeVisible();
  await expect(page.getByTestId("context-chip")).toHaveCount(0);
  await group.getByRole("button", { name: /, Manipal$/ }).click();
  await expect(answers(page)).toHaveCount(2, { timeout: LLM });
  await idle(page);
  expect(bodies).toHaveLength(2);
  expect(bodies[1].question).toBe(Q.kasturba);
  expect(typeof bodies[1].institute_id).toBe("number");
  await expect(page.getByTestId("turn-question")).toHaveCount(2);

  const last = answers(page).last();
  const names = last.getByTestId("record").locator("p.label-caps span[title]"); // InstituteName: full MCC name
  await expect(names.first()).toBeVisible();
  for (const t of await names.evaluateAll((els) => els.map((e) => e.getAttribute("title") ?? ""))) {
    expect(t).toMatch(/Manipal$|Manipal,/);
    expect(t).not.toContain("Mangalore");
  }
  const chip = page.getByTestId("context-chip");
  await expect(chip).toContainText("About: Kasturba Medical College");
  await expect(chip).toContainText(/Manipal$/);
  await expect(chip).not.toContainText("Mangalore");
  await page.waitForTimeout(900);
  await fullShot(page, path.join(SHOTS, "ask-clarify-pick-1440-light.png"));
  report("clarify-pick", seen);
});

test("New conversation clears the thread and the chip", async ({ page }) => {
  const seen = track(page);
  await page.goto("/#/ask");
  await send(page, Q.jodhpur);
  await expect(page.getByTestId("context-chip")).toBeVisible();
  await expect(page.getByTestId("turn")).toHaveCount(1);
  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByTestId("turn")).toHaveCount(0);
  await expect(page.getByTestId("context-chip")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "What would you like to check?" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Example questions" })).toBeVisible();
  await expect(page.getByLabel("Your question")).toBeFocused();
  await expect(page.getByRole("button", { name: "New conversation" })).toHaveCount(0);
  // Memory only: nothing written to web storage.
  const keys = await page.evaluate(() => [...Object.keys(localStorage), ...Object.keys(sessionStorage)]);
  expect(keys.filter((k) => k !== "neet-theme")).toEqual([]);
  report("new-conversation", seen);
});

test("a reply still pending when the chip is removed, or the conversation reset, does not set the chip", async ({ page }) => {
  const seen = track(page);
  const chip = page.getByTestId("context-chip");
  await page.goto("/#/ask");
  await send(page, Q.jodhpur);
  await expect(chip).toBeVisible();
  // Remove the chip while the next reply is pending.
  await page.getByLabel("Your question").fill(Q.jodhpur);
  await page.getByLabel("Your question").press("Enter");
  await expect(page.getByRole("status").filter({ hasText: "Checking against the source rows" })).toBeVisible();
  await page.getByRole("button", { name: "Remove institute context" }).click();
  await expect(answers(page)).toHaveCount(2, { timeout: LLM });
  await idle(page);
  await expect(chip).toHaveCount(0);
  // Start a new conversation while a reply is pending: the reply is dropped and sets nothing.
  await page.getByLabel("Your question").fill(Q.jodhpur);
  await page.getByLabel("Your question").press("Enter");
  await expect(page.getByRole("status").filter({ hasText: "Checking against the source rows" })).toBeVisible();
  const done = page.waitForResponse((r) => r.url().endsWith("/api/answer/ask"), { timeout: LLM });
  await page.getByRole("button", { name: "New conversation" }).click();
  await done;
  await page.waitForTimeout(500);
  await expect(page.getByTestId("turn")).toHaveCount(0);
  await expect(chip).toHaveCount(0);
  report("pending-chip-race", seen);
});
