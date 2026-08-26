import assert from "node:assert/strict";
import { test } from "node:test";
import { MIN_RATING_VOTES, titleRating } from "./rating.ts";

test("titleRating hides titles without annotated aggregates", () => {
  assert.equal(titleRating({ rating_average: null, rating_count: null }), null);
  assert.equal(titleRating({}), null);
});

test("titleRating hides scores below the vote threshold", () => {
  for (let count = 0; count < MIN_RATING_VOTES; count += 1) {
    assert.equal(titleRating({ rating_average: 9, rating_count: count }), null);
  }
});

test("titleRating formats the average at and above the threshold", () => {
  assert.deepEqual(titleRating({ rating_average: 8.5, rating_count: MIN_RATING_VOTES }), {
    average: "8.5",
    count: MIN_RATING_VOTES,
  });
  const badge = titleRating({ rating_average: 7, rating_count: 12 });
  assert.ok(badge);
  assert.equal(badge.average, "7.0");
});

test("titleRating treats a missing count as zero votes", () => {
  assert.equal(titleRating({ rating_average: 9.1, rating_count: undefined }), null);
});
