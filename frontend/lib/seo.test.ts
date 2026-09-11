import assert from "node:assert/strict";
import { test } from "node:test";
import { SITE_URL } from "./site.ts";
import {
  catalogPageExists,
  catalogSeoState,
  franchiseSeoState,
  jsonLdScript,
  titleOpenGraphType,
  titleSchemaType,
  titleWatchHref,
  websiteJsonLd,
} from "./seo.ts";

test("catalog base and pagination remain self-canonical and indexable", () => {
  assert.deepEqual(catalogSeoState({}), { canonical: "/catalog", index: true });
  assert.deepEqual(catalogSeoState({ page: 3 }), { canonical: "/catalog?page=3", index: true });
  assert.deepEqual(
    catalogSeoState({ seasons: "grouped", page: 2 }),
    { canonical: "/catalog?page=2", index: true },
  );
});

test("catalog search, facets and sorting consolidate into the base catalog", () => {
  for (const filters of [{ q: "anime" }, { genre: "action", page: 2 }, { ordering: "popular" as const }, { seasons: "separate" as const }]) {
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
  assert.equal(titleOpenGraphType("movie"), "video.movie");
  assert.equal(titleOpenGraphType("anime"), "video.tv_show");
  assert.deepEqual(websiteJsonLd("ru"), {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Anicast",
    alternateName: "АниКаст",
    url: SITE_URL,
    inLanguage: "ru",
  });
});

test("watch links keep playback on the title page and preserve its state", () => {
  assert.equal(
    titleWatchHref("31240-rezero-kara-hajimeru-isekai-seikatsu", 1, "306fb52e8ee8170c"),
    "/titles/31240-rezero-kara-hajimeru-isekai-seikatsu?episode=1&voice=306fb52e8ee8170c#watch",
  );
  assert.equal(titleWatchHref("title", "invalid"), "/titles/title?episode=1#watch");
  assert.equal(titleWatchHref("title", 3, " dub "), "/titles/title?episode=3&voice=dub#watch");
});

test("franchise index keeps pagination indexable and consolidates search", () => {
  assert.deepEqual(franchiseSeoState({}), { canonical: "/franchises", index: true });
  assert.deepEqual(franchiseSeoState({ page: 2 }), { canonical: "/franchises?page=2", index: true });
  assert.deepEqual(franchiseSeoState({ query: "gundam" }), { canonical: "/franchises", index: false });
  assert.deepEqual(
    franchiseSeoState({ query: "gundam", page: 3 }),
    { canonical: "/franchises", index: false },
  );
  assert.deepEqual(franchiseSeoState({ page: 99 }, false), { canonical: "/franchises", index: false });
});

test("json-ld payloads cannot break out of their script element", () => {
  // Synopses come from an external importer, so a closing tag inside the text
  // would otherwise end the script early and turn the rest into markup.
  const html = jsonLdScript({ description: "spoiler </script><img src=x onerror=alert(1)>" });
  assert.equal(html.includes("</script"), false);
  assert.equal(html.includes("<img"), false);
  assert.equal(
    JSON.parse(html).description,
    "spoiler </script><img src=x onerror=alert(1)>",
  );
  assert.equal(jsonLdScript({ text: "line\u2028break" }).includes("\u2028"), false);
});
