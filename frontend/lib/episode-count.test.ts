import assert from "node:assert/strict";
import test from "node:test";
import { createTranslator } from "../i18n/translate.ts";
import { dictionaries } from "../i18n/dictionaries.ts";
import { episodeCountLabel } from "./episode-count.ts";


test("episodeCountLabel picks the correct Russian plural form", () => {
  const t = createTranslator(dictionaries.ru);
  assert.equal(episodeCountLabel(t, "ru", 1), "1 серия");
  assert.equal(episodeCountLabel(t, "ru", 12), "12 серий");
  // 21 drives the "one" category despite the plural-looking last digit.
  assert.equal(episodeCountLabel(t, "ru", 21), "21 серия");
  assert.equal(episodeCountLabel(t, "ru", 22), "22 серии");
});

test("episodeCountLabel collapses English plural forms to episodes", () => {
  const t = createTranslator(dictionaries.en);
  assert.equal(episodeCountLabel(t, "en", 1), "1 episode");
  assert.equal(episodeCountLabel(t, "en", 12), "12 episodes");
});
