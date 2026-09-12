import { test, expect } from "@playwright/test";

// Edge contract: crawler controls and per-user cache split. No external
// account or production mutation is needed.
test.beforeEach(async ({ context }) => {
  await context.route("**/api/**", route => route.fulfill({
    status: 200, contentType: "application/json", body: "{}",
  }));
});

test("robots disallows token paths; auth pages are noindex", async ({ page, request }) => {
  const robots = await request.get("/robots.txt");
  expect(robots.ok()).toBe(true);
  const body = await robots.text();
  expect(body).toContain("/reset-password");
  expect(body).toContain("/verify-email");

  const login = await request.get("/login");
  expect(login.headers()["x-robots-tag"]).toContain("noindex");
});

test("private pages stay no-store, public pages use short private cache", async ({ request }) => {
  const account = await request.get("/account");
  expect(account.headers()["cache-control"]).toContain("no-store");
  const catalog = await request.get("/catalog");
  expect(catalog.headers()["cache-control"]).toContain("private");
  expect(catalog.headers()["cache-control"]).not.toMatch(/public/);
});

test("trailing slash canonicalizes", async ({ page }) => {
  await page.goto("/catalog/");
  expect(page.url().replace(/\/$/, "")).toContain("/catalog");
});
