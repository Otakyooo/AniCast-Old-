import assert from "node:assert/strict";
import { test } from "node:test";
import {
  filterEpisodeNumbers,
  firstRankedPlayableGroupKey,
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

test("voice kinds produce concise inline type labels", () => {
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
  assert.deepEqual(groups.map((group) => group.key), ["kodik:dub:610", "kodik:sub:99"]);
});

test("default voice follows API rank but skips options without a current playable source", () => {
  const groups = [
    { key: "animedia", episode_numbers: [1, 2, 3] },
    { key: "subtitles", episode_numbers: [1, 2, 3, 1150] },
    { key: "fallback", episode_numbers: [1150] },
  ];
  assert.equal(firstRankedPlayableGroupKey(groups, ["subtitles", "fallback"], 1150), "subtitles");
  assert.equal(firstRankedPlayableGroupKey(groups, ["fallback"], 1150), "fallback");
  assert.equal(firstRankedPlayableGroupKey(groups, ["external"], 1150), "external");
  assert.equal(firstRankedPlayableGroupKey(groups, [], 1150), "animedia");
});
