import assert from "node:assert/strict";
import { test } from "node:test";
import { createRequire } from "node:module";

// The test imports the deployed next.config.ts itself - not a copy of its
// rules - so a config change can never drift away from these expectations.
// API_INTERNAL_URL is read inside rewrites(), not at import time.
process.env.API_INTERNAL_URL = "http://127.0.0.1:8000";
const { default: nextConfig } = await import("../next.config.ts");

const require = createRequire(import.meta.url);
const { getPathMatch } = require("next/dist/shared/lib/router/utils/path-match.js");
const { prepareDestination } = require("next/dist/shared/lib/router/utils/prepare-destination.js");

const BACKEND = "http://127.0.0.1:8000";
// next.config types rewrites() as array | grouped form; this config deploys
// the flat array shape, so the test narrows it explicitly.
const rules = (await nextConfig.rewrites!()) as { source: string; destination: string }[];

/** Resolve a browser path through the deployed rules, as Next does. */
function rewrite(pathname: string): string | null {
  for (const rule of rules) {
    const match = getPathMatch(rule.source, { removeUnnamedParams: true, strict: true })(pathname);
    if (!match) continue;
    const resolved = prepareDestination({ appendParamsToQuery: true, destination: rule.destination, params: { ...match }, query: {} });
    const port = resolved.parsedDestination.port ? `:${resolved.parsedDestination.port}` : "";
    return `${resolved.parsedDestination.protocol}//${resolved.parsedDestination.hostname}${port}${resolved.parsedDestination.pathname}`;
  }
  return null;
}

test("deployed rewrite table pins the Django API slash semantics", () => {
  assert.deepEqual(rules, [
    { source: "/api/v1/media/posters/:filename", destination: `${BACKEND}/api/v1/media/posters/:filename` },
    { source: "/api/:path*/", destination: `${BACKEND}/api/:path*/` },
    { source: "/api/:path*", destination: `${BACKEND}/api/:path*/` },
  ]);
});

test("API rewrite preserves Django slash semantics without doubling it", () => {
  // Regression for the two shapes browsers actually send: Django list/detail
  // routes end with a slash, poster files do not.
  assert.equal(rewrite("/api/v1/titles/"), `${BACKEND}/api/v1/titles/`);
  assert.equal(rewrite("/api/v1/titles"), `${BACKEND}/api/v1/titles/`);
  assert.equal(rewrite("/api/v1/media/posters/x-m-abcdef12.jpg"), `${BACKEND}/api/v1/media/posters/x-m-abcdef12.jpg`);
  // Real slashed endpoints the app calls today: under the previous single
  // rule these never reached Django (Next 404), so they anchor the fix.
  assert.equal(rewrite("/api/v1/community/ratings/some-title/"), `${BACKEND}/api/v1/community/ratings/some-title/`);
  const resolved = ["/api", "/api/", "/api/v1/titles", "/api/v1/titles/", "/api/v1/community/ratings/some-title/"].map(rewrite) as string[];
  for (const url of resolved) {
    assert.ok(!url.replace("http://", "").includes("//"), `doubled slash in ${url}`);
  }
});

test("dropping the slashed variant would miss slashed API paths", () => {
  // Documents why both variants are deployed: with only "/api/:path*" the
  // strict Next matcher leaves "/api/v1/titles/" unmatched (falls through to
  // Next 404 instead of Django).
  const withoutSlashVariant = rules.filter(rule => rule.source !== "/api/:path*/");
  const match = getPathMatch(withoutSlashVariant[1].source, { removeUnnamedParams: true, strict: true })("/api/v1/titles/");
  assert.equal(match, false);
});
