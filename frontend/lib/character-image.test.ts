import assert from "node:assert/strict";
import { test } from "node:test";
import { CHARACTER_FALLBACK_IMAGE, characterImage, hasCharacterArt } from "./character-image.ts";

test("characterImage accepts only AniCast media and otherwise uses our brand mark", () => {
  assert.equal(characterImage("https://shikimori.io/assets/globals/missing_original.jpg"), CHARACTER_FALLBACK_IMAGE);
  assert.equal(characterImage("https://shikimori.io/assets/globals/missing_original.jpg?1711947446"), CHARACTER_FALLBACK_IMAGE);
  assert.equal(characterImage(""), CHARACTER_FALLBACK_IMAGE);
  assert.equal(characterImage(undefined), CHARACTER_FALLBACK_IMAGE);
  assert.equal(characterImage("https://example.invalid/portrait.jpg"), CHARACTER_FALLBACK_IMAGE);
  assert.equal(characterImage("/api/v1/media/posters/x-s-aabbccdd.jpg"), "/api/v1/media/posters/x-s-aabbccdd.jpg");
  assert.equal(
    characterImage("https://anicast.online/api/v1/media/posters/x-s-aabbccdd.jpg"),
    "https://anicast.online/api/v1/media/posters/x-s-aabbccdd.jpg",
  );
});

test("hasCharacterArt reports whether real artwork exists", () => {
  assert.equal(hasCharacterArt("https://shikimori.io/assets/globals/missing_original.jpg"), false);
  assert.equal(hasCharacterArt(""), false);
  assert.equal(hasCharacterArt(null), false);
  assert.equal(hasCharacterArt("https://example.invalid/portrait.jpg"), false);
  assert.equal(hasCharacterArt("/api/v1/media/posters/x-s-aabbccdd.jpg"), true);
});
