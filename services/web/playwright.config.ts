import { defineConfig } from "@playwright/test";

// Self-checks against the live local stack (answer :8002, predictor :8003) through the Vite dev
// server. Uses the Chromium build already in ~/Library/Caches/ms-playwright (1.59.1 -> chromium 1217).
export default defineConfig({
  testDir: "tests",
  timeout: 15 * 60_000,
  expect: { timeout: 120_000 },
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:5173", actionTimeout: 30_000 },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
