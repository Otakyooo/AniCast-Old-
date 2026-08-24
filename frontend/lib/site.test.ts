import assert from "node:assert/strict";
import { test } from "node:test";
import { SITE_URL, absoluteUrl, metaDescription } from "./site.ts";

test("absoluteUrl prefixes same-origin paths with the site origin", () => {
  assert.equal(absoluteUrl("/titles/cowboy-bebop"), `${SITE_URL}/titles/cowboy-bebop`);
  assert.equal(absoluteUrl("titles/cowboy-bebop"), `${SITE_URL}/titles/cowboy-bebop`);
});

test("absoluteUrl leaves remote and already-absolute URLs untouched", () => {
  assert.equal(absoluteUrl("https://cdn.example.com/a.jpg"), "https://cdn.example.com/a.jpg");
  assert.equal(absoluteUrl(`${SITE_URL}/x`), `${SITE_URL}/x`);
});

test("metaDescription normalizes whitespace and truncates with ellipsis", () => {
  const text = "  line one\nline two\twith  spaces  ";
  assert.equal(metaDescription(text, "fallback"), "line one line two with spaces");
  const long = "а".repeat(400);
  const cut = metaDescription(long, "fallback");
  assert.equal(cut.length, 300);
  assert.ok(cut.endsWith("…"));
});

test("metaDescription falls back when text is missing or blank", () => {
  assert.equal(metaDescription(null, "fallback"), "fallback");
  assert.equal(metaDescription("   \n  ", "fallback"), "fallback");
});
