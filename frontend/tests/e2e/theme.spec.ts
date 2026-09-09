import { test, expect } from "@playwright/test";

// Exercise the real production shell with anonymous API fixtures. No external
// account, mail delivery, catalogue fixture or production mutation is needed.
test.beforeEach(async ({ context }) => {
  await context.route("**/api/**", route => route.fulfill({
    status: route.request().url().includes("/auth/me/") ? 401 : 200,
    contentType: "application/json", body: "{}",
  }));
});

test("explicit themes persist; logo stays transparent and navigation readable", async ({ page, context }, info) => {
  await page.emulateMedia({ colorScheme: "light" });
  const response = await page.goto("/backup-privacy");
  const root = page.locator("html");
  await expect(root).toHaveAttribute("data-theme", "dark");
  const switcher = page.getByLabel("Тема оформления", { exact: true });
  await expect(switcher.locator("option")).toHaveCount(2);
  const policy = response!.headers()["content-security-policy"];
  const nonce = policy.match(/'nonce-([^']+)'/)![1];
  expect(policy).toContain("script-src-attr 'none'");
  expect(response!.headers()["cache-control"]).toContain("no-store");
  expect(await page.locator("script:not([src])").evaluateAll(elements => elements.every(el => Boolean((el as HTMLScriptElement).nonce)))).toBe(true);

  for (const theme of ["light", "dark"] as const) {
    await switcher.selectOption(theme);
    await expect(root).toHaveAttribute("data-theme", theme);
    await expect(page.locator(".brand-logo").first()).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    // Check the actual computed text colors, not just the token source file.
    await expect(page.locator(".primary-nav a:not(.active)").first()).toHaveCSS("color", theme === "light" ? "rgb(116, 97, 81)" : "rgb(203, 180, 154)");
    const contrast = await page.locator(".primary-nav a:not(.active)").first().evaluate(el => {
      const rgb = (s: string) => (s.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
      const luminance = (c: number[]) => c.map(n => n / 255).map(n => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4).reduce((s, n, i) => s + n * [.2126, .7152, .0722][i], 0);
      const fg = luminance(rgb(getComputedStyle(el).color));
      const bg = luminance(rgb(getComputedStyle(document.querySelector(".global-nav")!).backgroundColor));
      return (Math.max(fg, bg) + .05) / (Math.min(fg, bg) + .05);
    });
    expect(contrast).toBeGreaterThanOrEqual(4.5);
    await page.screenshot({ path: info.outputPath(`${theme}.png`) });
  }
  await switcher.selectOption("light");
  const reload = await page.reload();
  await expect(root).toHaveAttribute("data-theme", "light");
  expect(reload!.headers()["content-security-policy"]).not.toContain(`'nonce-${nonce}'`);
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(root).toHaveAttribute("data-theme", "light");
  const other = await context.newPage();
  await other.goto("/backup-privacy");
  await other.getByLabel("Тема оформления", { exact: true }).selectOption("dark");
  await expect(root).toHaveAttribute("data-theme", "dark");
  await other.close();
});

test("legacy system preference becomes dark and does not follow the OS", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("anicast-theme", "system"));
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/backup-privacy");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByLabel("Тема оформления", { exact: true })).toHaveValue("dark");
});

test("switching still works when browser storage is unavailable", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", { get() { throw new DOMException("Blocked", "SecurityError"); } });
  });
  await page.goto("/backup-privacy");
  const switcher = page.getByLabel("Тема оформления", { exact: true });
  await switcher.focus();
  await expect(switcher).toBeFocused();
  await switcher.selectOption("light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("header links remain reachable and search fits the viewport", async ({ page }) => {
  await page.goto("/backup-privacy");
  const mobile = page.viewportSize()!.width < 768;
  if (mobile) {
    await page.getByRole("button", { name: "Открыть поиск", exact: true }).click();
  } else {
    const links = page.locator(".primary-nav > a");
    await expect(links).toHaveCount(6);
    for (const link of await links.all()) {
      await expect(link).toBeVisible();
      expect(await link.evaluate(el => {
        const r = el.getBoundingClientRect();
        return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)?.closest("a") === el;
      })).toBe(true);
    }
  }
  const input = page.getByRole("combobox", { name: "Поиск", exact: true });
  await expect(input).toBeVisible();
  await input.focus();
  await expect(input).toBeFocused();
  const bounds = await input.boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
  await input.press("Escape");
  if (mobile) {
    await expect(page.getByRole("button", { name: "Открыть поиск", exact: true })).toBeFocused();
  } else {
    await expect(input).toBeFocused();
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
