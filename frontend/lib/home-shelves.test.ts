import assert from "node:assert/strict";
import test from "node:test";
import { dedupeShelf, groupRecentEpisodesByTitle, planRecentEpisodeShelf } from "./home-shelves.ts";


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

interface RawRelease {
  air_date: string;
  title: { slug: string };
}

function release(air_date: string, slug = "x"): RawRelease {
  return { air_date, title: { slug } };
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
    compact: false,
  });
});

test("a thin week never shows releases older than the promised window", () => {
  const plan = planRecentEpisodeShelf(
    [
      release("2026-09-10"),
      release("2026-08-30"),
      release("2026-08-21"),
      release("2026-08-14"),
    ],
    "2026-09-10",
  );
  // Only the in-window row remains; older dates are never dishonestly composite.
  assert.deepEqual(plan, {
    items: [release("2026-09-10")],
    compact: true,
  });
});

test("empty or dateless weeks collapse into the compact layout", () => {
  assert.deepEqual(planRecentEpisodeShelf([], "2026-09-10"), { items: [], compact: true });
  const undated = [{ air_date: null, title: { slug: "u" } }, release("2026-09-10")];
  assert.deepEqual(planRecentEpisodeShelf(undated, "2026-09-10", 2), {
    items: [release("2026-09-10")],
    compact: true,
  });
});

test("groupRecentEpisodesByTitle merges a title's episodes to one card", () => {
  const items = [
    release("2026-09-10", "one-piece"),
    release("2026-09-09", "one-piece"),
    release("2026-09-08", "other"),
  ];
  const grouped = groupRecentEpisodesByTitle(items);
  assert.equal(grouped.length, 2);
  assert.equal(grouped[0].slug, "one-piece");
  assert.equal(grouped[0].extraCount, 1);
  // First row is the newest air date in the group.
  assert.equal(grouped[0].latestAirDate, "2026-09-10");
});
