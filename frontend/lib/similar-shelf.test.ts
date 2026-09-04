import assert from "node:assert/strict";
import { test } from "node:test";
import { dedupeByFranchise } from "./similar-shelf.ts";
import type { CatalogItem } from "./api.ts";

function item(slug: string, franchiseSlug?: string): CatalogItem {
  return {
    slug,
    name: slug,
    ...(franchiseSlug ? { franchise: { name: franchiseSlug, slug: franchiseSlug } } : {}),
  };
}

test("keeps one title per franchise", () => {
  const result = dedupeByFranchise([
    item("naruto", "naruto"),
    item("naruto-shippuden", "naruto"),
    item("fma-2003", "fma"),
    item("fma-brotherhood", "fma"),
    item("steins-gate"),
  ]);
  assert.deepEqual(
    result.map((entry) => entry.slug),
    ["naruto", "fma-2003", "steins-gate"],
  );
});

test("titles without franchise data always pass through", () => {
  const result = dedupeByFranchise([item("a"), item("b"), item("c")]);
  assert.equal(result.length, 3);
});
