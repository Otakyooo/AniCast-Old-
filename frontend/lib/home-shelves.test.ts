import assert from "node:assert/strict";
import test from "node:test";
import { dedupeShelf } from "./home-shelves.ts";


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
