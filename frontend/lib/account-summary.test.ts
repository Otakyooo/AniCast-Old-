import assert from "node:assert/strict";
import { test } from "node:test";
import type { AccountSummary } from "./auth.ts";
import { libraryTotalCount, pickRecentNotes, summaryWith } from "./account-summary.ts";

test("libraryTotalCount sums every status bucket", () => {
  assert.equal(
    libraryTotalCount({ planned: 2, watching: 3, completed: 0, on_hold: 1, dropped: 4 }),
    10,
  );
});

test("libraryTotalCount returns zero for an empty library", () => {
  assert.equal(libraryTotalCount({ planned: 0, watching: 0, completed: 0, on_hold: 0, dropped: 0 }), 0);
});

test("pickRecentNotes caps the preview at three entries", () => {
  assert.deepEqual(pickRecentNotes([1, 2, 3, 4, 5]), [1, 2, 3]);
  assert.deepEqual(pickRecentNotes([]), []);
});

test("summaryWith fills every field so stats never render undefined", () => {
  const summary = summaryWith({ favorites: 7 });
  for (const value of Object.values(summary.library)) assert.equal(value, 0);
  assert.equal(libraryTotalCount(summary.library), 0);
  assert.equal(summary.favorites, 7);
});
