import assert from "node:assert/strict";
import { test } from "node:test";
import { buildSearchOptionModel } from "./global-search.ts";

test("search option model preserves unique flat indexes across result groups", () => {
  const model = buildSearchOptionModel(
    {
      titles: [
        { slug: "frieren" },
        { slug: "dungeon-meshi" },
      ],
      characters: [{ slug: "fern" }],
      franchises: [{ slug: "fate" }],
    },
    "search",
    "Fate stay/night",
  );

  assert.deepEqual(model.starts, {
    titles: 0,
    characters: 2,
    franchises: 3,
  });
  assert.deepEqual(
    model.options.map(({ id, href }) => [id, href]),
    [
      ["search-title-frieren", "/titles/frieren"],
      ["search-title-dungeon-meshi", "/titles/dungeon-meshi"],
      ["search-character-fern", "/characters/fern"],
      ["search-franchise-fate", "/franchises/fate"],
      ["search-all", "/catalog?q=Fate%20stay%2Fnight"],
    ],
  );
});

test("search option model keeps later groups aligned when earlier groups are empty", () => {
  const model = buildSearchOptionModel(
    {
      titles: [],
      characters: [],
      franchises: [{ slug: "monogatari" }],
    },
    "search",
    "monogatari",
  );

  assert.equal(model.starts.franchises, 0);
  assert.equal(model.options[0]?.id, "search-franchise-monogatari");
  assert.equal(model.options[1]?.id, "search-all");
});
