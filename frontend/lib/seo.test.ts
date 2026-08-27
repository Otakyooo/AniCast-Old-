import assert from "node:assert/strict";
import { test } from "node:test";
import { SITE_URL } from "./site.ts";
import { catalogPageExists, catalogSeoState, titleSchemaType, websiteJsonLd } from "./seo.ts";

test("catalog base and pagination remain self-canonical and indexable", () => {
  assert.deepEqual(catalogSeoState({}), { canonical: "/catalog", index: true });
  assert.deepEqual(catalogSeoState({ page: 3 }), { canonical: "/catalog?page=3", index: true });
});

test("catalog search, facets and sorting consolidate into the base catalog", () => {
  for (const filters of [{ q: "anime" }, { genre: "action", page: 2 }, { ordering: "popular" as const }]) {
    assert.deepEqual(catalogSeoState(filters), { canonical: "/catalog", index: false });
  }
});

test("catalog pages outside the real result range are noindex", () => {
  assert.equal(catalogPageExists(100, 5), true);
  assert.equal(catalogPageExists(100, 6), false);
  assert.deepEqual(catalogSeoState({ page: 999 }, false), { canonical: "/catalog", index: false });
});

test("schema helpers describe the site and distinguish movies", () => {
  assert.equal(titleSchemaType("movie"), "Movie");
  assert.equal(titleSchemaType("anime"), "TVSeries");
  assert.deepEqual(websiteJsonLd("ru"), {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "AniCast",
    alternateName: "АниКаст",
    url: SITE_URL,
    inLanguage: "ru",
  });
});
