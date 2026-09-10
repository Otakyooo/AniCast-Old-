import assert from "node:assert/strict";
import test from "node:test";
import { dedupeShelf, planRecentEpisodeShelf } from "./home-shelves.ts";


function item(slug: string) {
  return { slug, name: slug };
}


test("dedupeShelf removes follower titles already shown by the lead shelf", () => {
  const lead = [item("a"), item("b")];
  const follower = [item("b"), item("c"), item("a"), item("d")];
  assert.deepEqual(dedupeShelf(lead, follower).map((entry) => entry.slug), ["c", "d"]);
});

test("dedupeShelf keeps the follower order and tolerates empty shelves", () => {
  assert.deepEqual(dedupeShelf([], [item("x"), item("y")]).map((entry) => entry.slug), ["x", "y"]);
  assert.deepEqual(dedupeShelf([item("x")], []), []);
});

function release(air_date: string) {
  return { air_date };
}

test("a dense release week fills the rail from the week alone", () => {
  const plan = planRecentEpisodeShelf(
    [
      release("2026-09-10"),
      release("2026-09-09"),
      release("2026-09-07"),
      release("2026-09-04"),
      release("2026-08-02"),
    ],
    "2026-09-10",
  );
  assert.deepEqual(plan, {
    items: [
      release("2026-09-10"),
      release("2026-09-09"),
      release("2026-09-07"),
      release("2026-09-04"),
    ],
    widened: false,
    compact: false,
  });
});

test("a thin week is filled from older releases instead of leaving a hole", () => {
  const items = [
    release("2026-09-10"),
    release("2026-08-30"),
    release("2026-08-21"),
    release("2026-08-14"),
  ];
  const plan = planRecentEpisodeShelf(items, "2026-09-10");
  assert.deepEqual(plan, { items, widened: true, compact: false });
});

test("too few releases switch the shelf to its compact layout", () => {
  const single = [release("2026-09-10")];
  assert.deepEqual(planRecentEpisodeShelf(single, "2026-09-10"), {
    items: single,
    widened: false,
    compact: true,
  });
  assert.deepEqual(planRecentEpisodeShelf([], "2026-09-10"), {
    items: [],
    widened: false,
    compact: true,
  });
  // Missing air dates never count as "this week", but still fill the shelf.
  const undated = [{ air_date: null }, release("2026-09-10")];
  assert.deepEqual(planRecentEpisodeShelf(undated, "2026-09-10", 2), {
    items: undated,
    widened: true,
    compact: false,
  });
});
