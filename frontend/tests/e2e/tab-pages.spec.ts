import { test, expect, type Page, type TestInfo } from "@playwright/test";

test.afterEach(async ({ page, context }) => {
  await page.unrouteAll({ behavior: "wait" });
  await context.unrouteAll({ behavior: "wait" });
});

async function captureThemes(page: Page, info: TestInfo, name: string) {
  // The theme switcher lives in the preferences menu (header shows only the
  // trigger since the 11.09 UX pass), so open it once before switching.
  await page.getByRole("button", { name: "Открыть предпочтения", exact: true }).click();
  for (const theme of ["light", "dark"] as const) {
    await page.getByLabel("Тема оформления", { exact: true }).selectOption(theme);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`tab-${name}-${theme}.png`), fullPage: true, animations: "disabled" });
  }
}

test("catalog filter chips synchronize fields; random title preserves selection and retries", async ({ page }, info) => {
  await page.goto("/catalog?q=Browser&status=finished");
  await expect(page.getByLabel("Поиск по каталогу", { exact: true })).toHaveValue("Browser");
  await page.getByRole("link", { name: "Сбросить: Поиск по каталогу", exact: true }).click();
  await expect(page).toHaveURL(/\/catalog\?status=finished$/);
  await expect(page.getByLabel("Поиск по каталогу", { exact: true })).toHaveValue("");
  await expect(page.getByRole("combobox", { name: "Статус выпуска", exact: true })).toHaveValue("finished");
  // A non-overflowing form can still squeeze its search input into a sliver.
  expect((await page.getByRole("textbox", { name: "Поиск по каталогу", exact: true }).boundingBox())!.width).toBeGreaterThanOrEqual(230);
  await captureThemes(page, info, "catalog");

  let calls = 0;
  await page.route("**/api/v1/titles/?**", async route => {
    const query = new URL(route.request().url()).searchParams;
    expect(query.get("page_size")).toBe("1");
    expect(query.get("status")).toBe("finished");
    calls++;
    if (calls === 1) await route.fulfill({ status: 503, json: {} });
    else await route.continue();
  });
  await page.getByRole("button", { name: "Случайный тайтл", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Не удалось выбрать тайтл");
  await expect(page).toHaveURL(/status=finished$/);
  await page.getByRole("button", { name: "Случайный тайтл", exact: true }).click();
  await expect(page).toHaveURL(/\/titles\/browser-fixture$/);
  expect(calls).toBe(2);
});

test("catalog server outage stays distinct from empty results and preserves page filters", async ({ page }) => {
  await page.goto("/catalog?q=e2e-unavailable&page=2");
  await expect(page.getByRole("heading", { name: "Каталог", exact: true })).toBeVisible();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Не удалось загрузить данные");
  await expect(page.getByText("Ничего не найдено", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Повторить", exact: true }).click();
  await expect(page.getByRole("button", { name: "Повторить", exact: true })).toBeEnabled();
  await expect(page.getByLabel("Поиск по каталогу", { exact: true })).toHaveValue("e2e-unavailable");
  await page.getByRole("link", { name: "Сбросить", exact: true }).click();
  await expect(page.getByText("Найдено: 1", { exact: true })).toBeVisible();
});

test("empty schedule keeps dated keyboard tabs; outages do not claim zero releases", async ({ page }, info) => {
  await page.goto("/schedule?week=2026-10-12");
  await expect(page.getByRole("tab")).toHaveCount(7);
  const first = page.getByRole("tab").first();
  await first.focus();
  await first.press("End");
  await expect(page.getByRole("tab").last()).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab").last().press("Tab");
  await expect(page.getByRole("tabpanel")).toBeFocused();
  await expect(page.getByRole("heading", { name: /18 октября/ })).toBeVisible();
  await captureThemes(page, info, "schedule");
  await page.goto("/schedule?week=2111-10-12");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Не удалось загрузить данные");
  await expect(page.getByText("На этой неделе релизов нет", { exact: true })).toHaveCount(0);
});

test("history exposes older pages and recovers from a failed request", async ({ page }, info) => {
  let failed = false;
  await page.route("**/api/v1/history/?**", route => {
    const query = new URL(route.request().url()).searchParams;
    if (query.get("page") === "2" && !failed) {
      failed = true;
      return route.fulfill({ status: 503, json: {} });
    }
    const second = query.get("page") === "2";
    return route.fulfill({ json: { count: 21, next: second ? null : "?page=2", previous: second ? "?page=1" : null,
      results: [{ title: { slug: "browser-fixture", name: second ? "Older fixture" : "Recent fixture" },
        episode: { id: second ? 2 : 1, number: second ? 2 : 1, name: "Fixture episode" }, is_watched: second }] } });
  });
  await page.goto("/history");
  await expect(page.getByText("Recent fixture", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Вперёд →", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Историю не удалось загрузить");
  await page.getByRole("button", { name: "Повторить", exact: true }).click();
  await expect(page.getByText("Older fixture", { exact: true })).toBeVisible();
  await expect(page.getByText("Страница 2 из 2", { exact: true })).toBeVisible();
  // The avatar may overlap the banner; identity text must stay on the opaque
  // content surface in both themes, including the two-line mobile guest copy.
  const identityHeading = page.getByRole("main").getByRole("heading", { level: 1 });
  expect(await identityHeading.evaluate(el => {
    const banner = el.closest("header")!.previousElementSibling!;
    return el.getBoundingClientRect().top >= banner.getBoundingClientRect().bottom;
  })).toBe(true);
  await captureThemes(page, info, "history");
  await page.reload();
  await expect(page.getByText("Older fixture", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "← Назад", exact: true }).click();
  await expect(page.getByText("Recent fixture", { exact: true })).toBeVisible();
});

test("library retries in place and selected view/filter remain visibly distinct", async ({ page }, info) => {
  let calls = 0;
  await page.route("**/api/v1/library/?**", route => {
    calls++;
    expect(new URL(route.request().url()).searchParams.get("status")).toBe("watching");
    return route.fulfill(calls === 1 ? { status: 503, json: {} } : { json: { count: 0, results: [] } });
  });
  await page.goto("/library?status=watching");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Не удалось выполнить запрос");
  await page.getByRole("button", { name: "Повторить", exact: true }).click();
  await expect(page.getByRole("link", { name: "Открыть каталог", exact: true })).toBeVisible();
  for (const name of ["Тайтлы", "Смотрю"]) {
    const link = page.getByRole("link", { name, exact: true });
    await expect(link).toHaveAttribute("aria-current", "page");
    const colors = await link.evaluate(el => [getComputedStyle(el).borderTopColor, getComputedStyle(el.parentElement!.querySelector('a:not([aria-current])')!).borderTopColor]);
    expect(colors[0]).not.toBe(colors[1]);
  }
  await captureThemes(page, info, "library");
  expect(calls).toBe(2);
});
