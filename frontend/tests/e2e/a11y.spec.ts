import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Automated WCAG gate for the key public flows. This replaces ad-hoc axe
// runs, not a screen-reader pass (NVDA/VoiceOver remain manual): it catches
// missing names, contrast and landmark regressions on every CI run.
const pages = [
  { name: "home", path: "/" },
  { name: "catalog", path: "/catalog" },
  { name: "title", path: "/titles/browser-fixture" },
  { name: "schedule", path: "/schedule" },
  { name: "login", path: "/login" },
] as const;

for (const { name, path } of pages) {
  test(`${name} has no serious or critical a11y violations`, async ({ page }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      // Provider player documents are third-party: their internals (e.g. a
      // Kodik error state WebKit rendered in CI) are out of scope. Our side
      // of the frame — sandbox, title, loading and error states — is covered
      // by the player specs and the checks above.
      .exclude("iframe")
      .analyze();
    const blocking = results.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    );
    expect(
      blocking.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        nodes: violation.nodes.length,
        target: violation.nodes.slice(0, 3).map((node) => node.target),
      })),
      `${name}: serious/critical a11y violations`,
    ).toEqual([]);
  });
}
