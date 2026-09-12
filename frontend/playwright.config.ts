import { defineConfig, devices } from "@playwright/test";

// Default CI runs Chromium viewports only (fast). Nightly/owner runs with
// E2E_BROWSERS=all add Firefox + WebKit desktop coverage for engine-specific
// CSP/fetch/image regressions. No extra cost until explicitly enabled.
const chromiumViewports = [
  { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
  { name: "laptop", use: { viewport: { width: 1280, height: 900 } } },
  { name: "tablet", use: { viewport: { width: 820, height: 1180 } } },
  { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
];

const extraBrowsers = process.env.E2E_BROWSERS === "all" ? [
  { name: "firefox-desktop", use: { ...devices["Desktop Firefox"], viewport: { width: 1440, height: 900 } } },
  { name: "webkit-desktop", use: { ...devices["Desktop Safari"], viewport: { width: 1440, height: 900 } } },
] : [];

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  maxFailures: process.env.CI ? 3 : 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure" },
  projects: [...chromiumViewports, ...extraBrowsers],
  webServer: [{
    command: "python tests/e2e/backend.py",
    url: "http://127.0.0.1:8000/health/live",
    env: { ANICAST_E2E: "1" },
    reuseExistingServer: false,
    timeout: 60_000,
  }, {
    command: "npm run start -- --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100/backup-privacy",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { INTERNAL_API_BASE_URL: "http://127.0.0.1:8000/api/v1" },
  }],
});
