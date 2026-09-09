import test from "node:test";
import assert from "node:assert/strict";
import { runInNewContext } from "node:vm";
import { THEME_SCRIPT } from "./theme.ts";

function browser(stored: string | null = null, dark = false, blocked = false) {
  const listeners = new Map<string, (event: { key?: string | null; newValue?: string | null; detail?: string }) => void>();
  const root = { dataset: {} as Record<string, string>, style: { colorScheme: "" } };
  const meta = { content: "" };
  let osChange = () => {};
  const media = { matches: dark, addEventListener: (_: string, fn: () => void) => { osChange = fn; } };
  let saved = stored;
  runInNewContext(THEME_SCRIPT, {
    document: { documentElement: root, querySelector: () => meta },
    window: { matchMedia: () => media, addEventListener: (name: string, fn: () => void) => listeners.set(name, fn), dispatchEvent: () => {} },
    Event: class {},
    localStorage: { getItem: () => { if (blocked) throw Error(); return stored; }, setItem: (_: string, value: string) => { if (blocked) throw Error(); saved = value; } },
  });
  return { root, meta, saved: () => saved, os: (value: boolean) => { media.matches = value; osChange(); }, select: (detail: string) => listeners.get("anicast-theme-change")!({ detail }), storage: (newValue: string | null) => listeners.get("storage")!({ key: "anicast-theme", newValue }) };
}
test("first paint defaults to dark and ignores OS changes and legacy system mode", () => {
  const b = browser(null, false);
  assert.equal(b.root.dataset.theme, "dark");
  b.os(false);
  assert.equal(b.root.dataset.theme, "dark");
  assert.equal(b.meta.content, "#171311");
  assert.equal(browser("system", false).root.dataset.themePreference, "dark");
});
test("explicit preference persists, overrides OS and synchronizes tabs", () => {
  const b = browser("light", true);
  assert.equal(b.root.dataset.theme, "light");
  b.select("dark"); b.os(false);
  assert.equal(b.saved(), "dark");
  assert.equal(b.root.dataset.theme, "dark");
  b.storage("light");
  assert.equal(b.root.dataset.theme, "light");
  b.storage(null); b.os(true);
  assert.equal(b.root.dataset.themePreference, "dark");
  assert.equal(b.root.dataset.theme, "dark");
});
test("invalid and unavailable storage do not prevent switching", () => {
  assert.equal(browser("invalid").root.dataset.themePreference, "dark");
  const b = browser(null, false, true);
  b.select("dark");
  assert.equal(b.root.dataset.theme, "dark");
  assert.equal(b.root.style.colorScheme, "dark");
});
