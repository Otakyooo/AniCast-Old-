import assert from "node:assert/strict";
import { test } from "node:test";
import { CHARACTER_FALLBACK_IMAGE, characterImage, hasCharacterArt } from "./character-image.ts";

test("characterImage swaps the shikimori missing-art filler for our mascot", () => {
  assert.equal(characterImage("https://shikimori.io/assets/globals/missing_original.jpg"), CHARACTER_FALLBACK_IMAGE);
  assert.equal(characterImage("https://shikimori.io/assets/globals/missing_original.jpg?1711947446"), CHARACTER_FALLBACK_IMAGE);
  assert.equal(characterImage(""), CHARACTER_FALLBACK_IMAGE);
  assert.equal(characterImage(undefined), CHARACTER_FALLBACK_IMAGE);
  assert.equal(
    characterImage("https://shikimori.io/system/characters/original/40882.jpg?1708821764"),
    "https://shikimori.io/system/characters/original/40882.jpg?1708821764",
  );
});

test("hasCharacterArt reports whether real artwork exists", () => {
  assert.equal(hasCharacterArt("https://shikimori.io/assets/globals/missing_original.jpg"), false);
  assert.equal(hasCharacterArt(""), false);
  assert.equal(hasCharacterArt(null), false);
  assert.equal(hasCharacterArt("https://shikimori.io/system/characters/original/40882.jpg"), true);
});
