import assert from "node:assert/strict";
import { test } from "node:test";
import { summarizeEpisodeCoverage } from "./episode-coverage.ts";

test("summarizeEpisodeCoverage normalizes and groups real episode numbers", () => {
  const input = [10, 2, 1, 2, -1, 1.5, 7, 8];
  assert.deepEqual(summarizeEpisodeCoverage(input), {
    count: 5,
    first: 1,
    last: 10,
    density: 0.5,
    availableRanges: ["1–2", "7–8", "10"],
    missingRanges: ["3–6", "9"],
  });
  assert.deepEqual(input, [10, 2, 1, 2, -1, 1.5, 7, 8]);
});

test("summarizeEpisodeCoverage handles empty, single and contiguous coverage", () => {
  assert.deepEqual(summarizeEpisodeCoverage([]), {
    count: 0,
    first: null,
    last: null,
    density: 0,
    availableRanges: [],
    missingRanges: [],
  });
  assert.deepEqual(summarizeEpisodeCoverage([7]), {
    count: 1,
    first: 7,
    last: 7,
    density: 1,
    availableRanges: ["7"],
    missingRanges: [],
  });
  assert.deepEqual(summarizeEpisodeCoverage([1, 2, 3]), {
    count: 3,
    first: 1,
    last: 3,
    density: 1,
    availableRanges: ["1–3"],
    missingRanges: [],
  });
});

test("summarizeEpisodeCoverage exposes shorter exclusions for dense coverage", () => {
  const animedia = [
    ...Array.from({ length: 268 }, (_, index) => index + 1),
    ...Array.from({ length: 8 }, (_, index) => index + 270),
    ...Array.from({ length: 844 }, (_, index) => index + 279),
  ];
  const summary = summarizeEpisodeCoverage(animedia);
  assert.deepEqual(summary.availableRanges, ["1–268", "270–277", "279–1122"]);
  assert.deepEqual(summary.missingRanges, ["269", "278"]);
  assert.equal(summary.count, 1120);
  assert.ok(summary.density > 0.99);
});

test("summarizeEpisodeCoverage exposes sparse coverage density", () => {
  const summary = summarizeEpisodeCoverage([1, 1000]);
  assert.equal(summary.density, 0.002);
  assert.deepEqual(summary.availableRanges, ["1", "1000"]);
  assert.deepEqual(summary.missingRanges, ["2–999"]);
});
