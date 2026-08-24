import assert from "node:assert/strict";
import { test } from "node:test";
import { dictionaries } from "../i18n/dictionaries.ts";

function extractKeys(value: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(value).flatMap(([key, child]) =>
    typeof child === "object" && child !== null
      ? extractKeys(child as Record<string, unknown>, prefix ? `${prefix}.${key}` : key)
      : [prefix ? `${prefix}.${key}` : key],
  );
}

test("every ru key has an en translation", () => {
  const ruKeys = extractKeys(dictionaries.ru);
  const missing = ruKeys.filter((key) => !(key in dictionaries.en));
  assert.deepEqual(missing, []);
});

test("account hub keys stay bilingual and interpolated", () => {
  for (const dictionary of [dictionaries.ru, dictionaries.en]) {
    assert.ok(dictionary["account.title"]);
    assert.match(dictionary["account.sectionLibraryHint"], /\{count\}/);
    assert.ok(dictionary["account.recentNotes"]);
  }
});
