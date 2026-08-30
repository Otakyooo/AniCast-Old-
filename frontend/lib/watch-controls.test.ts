import assert from "node:assert/strict";
import { test } from "node:test";
import {
  filterEpisodeNumbers,
  normalizeEpisodeNumbers,
  resolveRequestedGroupKey,
  voiceSection,
} from "./watch-controls.ts";

test("episode navigation normalizes provider data and jumps by number prefix", () => {
  assert.deepEqual(normalizeEpisodeNumbers([3, 1, 3, -1, 2.5, 2]), [1, 2, 3]);
  assert.deepEqual(filterEpisodeNumbers([1, 12, 120, 121, 212], "12"), [12, 120, 121]);
  assert.deepEqual(filterEpisodeNumbers([1, 12, 120], "episode 120"), [120]);
  assert.deepEqual(filterEpisodeNumbers([1, 2], "no number"), []);
});

test("voice kinds map into the three visible chooser sections", () => {
  assert.equal(voiceSection("dub"), "dub");
  assert.equal(voiceSection("voice"), "dub");
  assert.equal(voiceSection("sub"), "sub");
  assert.equal(voiceSection("raw"), "raw");
});

test("stable group keys win and legacy links resolve without becoming state", () => {
  const groups = [
    { key: "kodik:dub:610", legacy_key: "old-name-hash" },
    { key: "kodik:sub:99", legacy_key: null },
  ];
  assert.deepEqual(resolveRequestedGroupKey(groups, "kodik:dub:610"), {
    key: "kodik:dub:610",
    legacy: false,
  });
  assert.deepEqual(resolveRequestedGroupKey(groups, "old-name-hash"), {
    key: "kodik:dub:610",
    legacy: true,
  });
  assert.equal(resolveRequestedGroupKey(groups, "missing"), null);
});
