import { defineConfig, devices } from "@playwright/test";

const PORT = 3000;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  timeout: 60_000,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
  webServer: [
    {
      command: "node playwright/start-test-api.mjs",
      url: "http://127.0.0.1:8000/api/v1/health/ready",
      reuseExistingServer: true,
      timeout: 180_000,
    },
    {
      command: "npm run dev",
      url: `http://127.0.0.1:${PORT}`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        STATS_API_URL: "http://127.0.0.1:8000",
      },
    },
  ],
});
