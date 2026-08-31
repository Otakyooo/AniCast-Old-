import assert from "node:assert/strict";
import { test } from "node:test";
import {
  episodeNumberRanges,
  episodeRangeIndex,
  filterEpisodeNumbers,
  firstRankedPlayableGroupKey,
  mergeCurrentWatchSourceGroups,
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

test("long episode lists are split into stable bounded ranges", () => {
  const numbers = [3, 1, 2, ...Array.from({ length: 205 }, (_, index) => index + 4)];
  const ranges = episodeNumberRanges(numbers, 100);
  assert.deepEqual(ranges.map(({ first, last, numbers: rangeNumbers }) => ({
    first,
    last,
    count: rangeNumbers.length,
  })), [
    { first: 1, last: 100, count: 100 },
    { first: 101, last: 200, count: 100 },
    { first: 201, last: 208, count: 8 },
  ]);
  assert.equal(episodeRangeIndex(ranges, 150), 1);
  assert.equal(episodeRangeIndex(ranges, 999), 2);
});

test("episode ranges preserve gaps and reject invalid range sizes", () => {
  const ranges = episodeNumberRanges([1, 3, 7], 0);
  assert.deepEqual(ranges, [{ first: 1, last: 7, numbers: [1, 3, 7] }]);
  assert.equal(episodeRangeIndex(ranges, 2), 0);
  assert.equal(episodeRangeIndex([], 1), 0);
});

test("current episode sources repair a stale cached voice matrix", () => {
  const groups = [
    {
      key: "dub:1",
      name: "Old name",
      kind: "dub",
      provider_name: "Provider",
      episodes_count: 2,
      episode_numbers: [1, 2],
      popularity_percent: 90,
    },
    {
      key: "stale:3",
      name: "Stale option",
      kind: "dub",
      provider_name: "Provider",
      episodes_count: 2,
      episode_numbers: [3, 4],
      popularity_percent: 5,
    },
  ];
  const currentSources = [{
    id: 10,
    name: "Current name",
    kind: "dub",
    selection_key: "dub:1",
    availability: "available",
    is_available: true,
    playback_available: true,
  }, {
    id: 11,
    name: "Fresh option",
    kind: "sub",
    selection_key: "sub:2",
    availability: "available",
    is_available: true,
    playback_available: true,
  }];

  const merged = mergeCurrentWatchSourceGroups(groups, currentSources, 3);
  assert.deepEqual(merged.map((group) => ({
    key: group.key,
    name: group.name,
    numbers: group.episode_numbers,
    known: group.coverage_known,
  })), [
    { key: "dub:1", name: "Current name", numbers: [1, 2, 3], known: true },
    { key: "stale:3", name: "Stale option", numbers: [4], known: true },
    { key: "sub:2", name: "Fresh option", numbers: [3], known: false },
  ]);
  assert.deepEqual(
    mergeCurrentWatchSourceGroups(groups, currentSources.slice(1), 3, true).map((group) => group.key),
    ["sub:2"],
  );
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
