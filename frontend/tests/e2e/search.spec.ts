import { test, expect } from "@playwright/test";

test("clearing or replacing a query cannot show stale results or selection", async ({ page }) => {
  let release!: () => void;
  let reached!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const requested = new Promise<void>(resolve => { reached = resolve; });
  await page.route("**/api/v1/search/**", async route => {
    const query = new URL(route.request().url()).searchParams.get("q");
    if (query === "old") { reached(); await held; }
    await route.fulfill({ contentType: "application/json", json: {
      titles: [{ slug: "browser-fixture", name: `${query} result`, year: 2026 }],
      characters: [], franchises: [],
    } });
  });
  await page.goto("/backup-privacy");
  if (page.viewportSize()!.width < 768) {
    await page.getByRole("button", { name: "Открыть поиск", exact: true }).click();
  }
  const search = page.getByRole("combobox", { name: "Поиск", exact: true });
  await search.fill("old");
  await requested;
  await search.fill("new");
  await expect(page.getByRole("option").filter({ hasText: "new result" })).toBeVisible();
  await search.press("ArrowDown");
  await expect(search).toHaveAttribute("aria-activedescendant", /.+/);
  release();
  await search.clear();
  await expect(page.getByRole("option")).toHaveCount(0);
  await expect(search).not.toHaveAttribute("aria-activedescendant");
  await search.fill("new");
  await expect(page.getByRole("option").filter({ hasText: "new result" })).toBeVisible();
  await expect(page.getByText("old result", { exact: true })).toHaveCount(0);
  await search.press("ArrowDown");
  await search.press("Enter");
  await expect(page).toHaveURL(/\/titles\/browser-fixture$/);
});
