import { test, expect, type Page, type TestInfo } from "@playwright/test";

const password = "Browser-fixture-passphrase-2042";
const titlePath = "/titles/browser-fixture?episode=1#watch";
const progressPath = "/api/v1/episodes/browser-fixture/1/progress/";

async function login(page: Page, info: TestInfo, scenario: string) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(`${info.project.name}-${scenario}@example.invalid`);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page.locator("form").getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/account$/);
  await expect(page.getByRole("heading", { name: `Fixture ${info.project.name} ${scenario}`, exact: true })).toBeVisible();
}

// The signed URL and redirect are real Django responses. Only the terminal
// provider document is replaced, retaining the iframe's actual origin/window.
async function stubVideo(page: Page) {
  await page.context().route("**/api/v1/playback/**", async route => {
    const response = await route.fetch({ maxRedirects: 0 });
    expect(response.status()).toBe(302);
    const target = response.headers().location;
    expect(new URL(target).origin).toBe("https://kodikplayer.com");
    // Playwright routes only the first request in an HTTP redirect chain.
    // Verify the real resolver, then start a document navigation so the
    // external-frame fixture below also intercepts the terminal URL.
    await route.fulfill({ status: 200, contentType: "text/html",
      body: `<script>location.replace(${JSON.stringify(target)})</script>` });
  });
  await page.context().route("https://kodikplayer.com/**", route => route.fulfill({
    contentType: "text/html",
    body: `<!doctype html><title>Video fixture</title>
      <button id="duration">Duration</button><button id="play">Play</button>
      <button id="pause">Pause at 180</button><button id="end">End</button>
      <output id="seek">none</output>
      <script>
      const send = (key, value) => parent.postMessage({key, value}, 'http://127.0.0.1:3100');
      document.querySelector('#duration').onclick = () => send('kodik_player_duration_update', 1200);
      document.querySelector('#play').onclick = () => send('kodik_player_video_started');
      document.querySelector('#pause').onclick = () => { send('kodik_player_time_update', 180); send('kodik_player_pause'); };
      document.querySelector('#end').onclick = () => send('kodik_player_video_ended');
      addEventListener('message', event => {
        if (event.source === parent && event.origin === 'http://127.0.0.1:3100' && event.data?.value?.method === 'seek') {
          document.querySelector('#seek').textContent = String(event.data.value.seconds);
        }
      });
      </script>`,
  }));
}

test("login rejects invalid credentials and CSRF; logout/expiry remove private identity", async ({ page, context }, info) => {
  const canonical = await context.request.get("/login/?from=test", { maxRedirects: 0 });
  expect(canonical.status()).toBe(308);
  expect(new URL(canonical.headers().location, canonical.url()).href).toBe("http://127.0.0.1:3100/login?from=test");
  const csrf = await context.request.get("/api/v1/auth/csrf/", { maxRedirects: 0 });
  expect(csrf.status()).toBe(200);
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(`${info.project.name}-auth@example.invalid`);
  await page.getByLabel("Пароль", { exact: true }).fill("invalid-passphrase");
  await page.locator("form").getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.locator("form").getByRole("alert")).toBeVisible();
  expect([401, 403]).toContain((await context.request.get("/api/v1/auth/me/")).status());
  expect((await context.request.post("/api/v1/auth/login/", {
    data: { email: `${info.project.name}-auth@example.invalid`, password },
    headers: { Origin: "http://127.0.0.1:3100" },
  })).status()).toBe(403);
  await login(page, info, "auth");
  const session = (await context.cookies()).find(cookie => cookie.name === "sessionid")!;
  expect(session.httpOnly).toBe(true);
  expect((await context.request.get("/api/v1/library/")).status()).toBe(200);
  await page.getByRole("button", { name: "Выйти", exact: true }).first().click();
  await expect(page).toHaveURL(/\/$/);
  expect([401, 403]).toContain((await context.request.get("/api/v1/auth/me/")).status());
  await login(page, info, "auth");
  await context.clearCookies({ name: "sessionid" });
  await page.reload();
  await expect(page.getByRole("heading", { name: `Fixture ${info.project.name} auth`, exact: true })).toHaveCount(0);
  expect((await context.request.get("/api/v1/library/")).status()).toBe(403);
});

test("player restores position, rejects forged messages, saves pause and completion", async ({ page, context }, info) => {
  await stubVideo(page);
  await login(page, info, "player");
  await page.goto(titlePath);
  const frame = page.frameLocator("#watch iframe");
  await frame.getByRole("button", { name: "Duration", exact: true }).click();
  await expect(frame.locator("#seek")).toHaveText("120");
  // Matching origin text alone is insufficient: the source window must be
  // the active iframe. This dispatch must neither start nor finish playback.
  await page.evaluate(() => window.dispatchEvent(new MessageEvent("message", {
    origin: "https://kodikplayer.com", source: window,
    data: { key: "kodik_player_video_ended" },
  })));
  expect((await (await context.request.get(progressPath)).json()).is_watched).toBe(false);
  await frame.getByRole("button", { name: "Play", exact: true }).click();
  await frame.getByRole("button", { name: "Pause at 180", exact: true }).click();
  await expect.poll(async () => (await (await context.request.get(progressPath)).json()).watched_seconds).toBe(180);
  await page.reload();
  await frame.getByRole("button", { name: "Duration", exact: true }).click();
  await expect(frame.locator("#seek")).toHaveText("180");
  await frame.getByRole("button", { name: "End", exact: true }).click();
  await expect.poll(async () => (await (await context.request.get(progressPath)).json()).is_watched).toBe(true);
  await expect(page.locator("#watch").getByText("Серия просмотрена", { exact: true })).toBeVisible();
  // Completion must survive a source change and cannot be overwritten by a
  // delayed watched-mark response for the same title.
  await page.locator("#watch").getByRole("button", { name: "Beta", exact: true }).click();
  await expect(page.locator("#watch").getByRole("button", { name: "Beta", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("guest player retries a failed source; late response cannot replace the new voice or episode", async ({ page }) => {
  await stubVideo(page);
  let attempts = 0;
  await page.route("**/api/v1/sources/*/playback/**", async route => {
    attempts++;
    if (attempts === 1) return route.fulfill({ status: 503, body: "{}", contentType: "application/json" });
    return route.continue();
  });
  await page.goto(titlePath);
  await page.locator("#watch").getByRole("button", { name: "Повторить", exact: true }).click();
  await expect(page.frameLocator("#watch iframe").getByRole("button", { name: "Play", exact: true })).toBeVisible();
  await expect(page.locator("#watch").getByText("Войдите, чтобы сохранять прогресс", { exact: true })).toBeVisible();

  let release!: () => void;
  let reached!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const requested = new Promise<void>(resolve => { reached = resolve; });
  await page.route("**/api/v1/sources/*/playback/**", async route => {
    const response = await route.fetch();
    reached();
    await held;
    await route.fulfill({ response });
  }, { times: 1 });
  await page.locator("#watch").getByRole("button", { name: "Beta", exact: true }).click();
  await requested;
  await page.locator("#watch").getByRole("button", { name: "Alpha", exact: true }).click();
  release();
  await expect.poll(() => page.frames().some(frame => frame.url().includes("fixture-1-Alpha"))).toBe(true);
  await expect(page.locator("#watch iframe")).toHaveCount(1);
  await page.goto("/titles/browser-fixture?episode=2#watch");
  await expect.poll(() => page.frames().some(frame => frame.url().includes("fixture-2-Alpha"))).toBe(true);
  await expect(page.locator("#watch iframe")).toHaveCount(1);
});
