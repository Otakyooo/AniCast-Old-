import type { MetadataRoute } from "next";
import { getCatalog, getCharacters, getFranchises } from "../lib/api";
import { SITE_URL } from "../lib/site";

// Sitemap must reflect the live catalog on every request, not the state at
// build time; a short TTL cache bounds the upstream crawl cost.
export const dynamic = "force-dynamic";

// The catalog changes rarely, but an uncached sitemap request crawls every page
// of every source endpoint. A short in-process TTL keeps the document fresh
// enough for crawlers while making repeat requests instant.
const SITEMAP_TTL_MS = 10 * 60 * 1000;
let sitemapCache: { at: number; entries: MetadataRoute.Sitemap } | null = null;

// 50 is the backend's max_page_size, so this is the fewest possible requests.
const PAGE_SIZE = 50;
// Enough for every entity at current volume with room to grow: characters are
// the largest set at ~7k rows, i.e. ~141 pages. The cap exists to bound a
// runaway loop, not to trim the document — when it was 25 it silently truncated
// characters at 500 of 7007, which is the kind of limit nobody notices.
const MAX_PAGES = 400;
// Pages are fetched in parallel batches: sequentially, 141 requests at ~0.15s
// each made the first uncached request take ~20s, long enough for a crawler to
// give up. Five at a time keeps that near 5s without hammering the backend.
const BATCH_SIZE = 5;

interface Paged<T> {
  count: number;
  results: T[];
}

/**
 * Walk a paginated public endpoint until it is exhausted.
 *
 * The first page reveals the total, so the remaining pages are fetched in
 * parallel batches instead of one at a time. Any API failure degrades to the
 * entries collected so far — the sitemap still ships with whatever is known
 * instead of erroring like the pages do.
 */
async function collectAll<T>(fetchPage: (page: number) => Promise<Paged<T>>): Promise<T[]> {
  let first: Paged<T>;
  try {
    first = await fetchPage(1);
  } catch {
    return [];
  }
  const collected = [...(first.results ?? [])];
  if (!collected.length) return collected;

  const total = Math.max(first.count, 0);
  const pageCount = Math.min(Math.ceil(total / Math.max(collected.length, 1)), MAX_PAGES);

  for (let page = 2; page <= pageCount; page += BATCH_SIZE) {
    const batch = [];
    for (let offset = 0; offset < BATCH_SIZE && page + offset <= pageCount; offset += 1) {
      batch.push(fetchPage(page + offset));
    }
    const settled = await Promise.allSettled(batch);
    for (const outcome of settled) {
      if (outcome.status === "rejected") return collected;
      collected.push(...(outcome.value.results ?? []));
    }
    if (collected.length >= total) break;
  }
  return collected;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = Date.now();
  if (sitemapCache && now - sitemapCache.at < SITEMAP_TTL_MS) {
    return sitemapCache.entries;
  }
  const entries = await buildSitemap();
  // A failed upstream crawl degrades to static routes inside buildSitemap;
  // the stale snapshot is still strictly better, so only cache successes.
  sitemapCache = { at: now, entries };
  return entries;
}

async function buildSitemap(): Promise<MetadataRoute.Sitemap> {
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/catalog`, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/schedule`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/franchises`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${SITE_URL}/media`, changeFrequency: "weekly", priority: 0.4 },
    { url: `${SITE_URL}/community`, changeFrequency: "daily", priority: 0.5 },
  ];

  const [titles, characters, franchises] = await Promise.all([
    collectAll((page) => getCatalog({ page, pageSize: PAGE_SIZE })),
    collectAll((page) => getCharacters("", page, PAGE_SIZE)),
    collectAll((page) => getFranchises(page, "", PAGE_SIZE)),
  ]);

  return [
    ...staticRoutes,
    ...titles.map((title) => ({
      url: `${SITE_URL}/titles/${title.slug}`,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    // Franchises are hub pages by construction: the list endpoint only returns
    // those with more than one title, so every entry connects several works.
    ...franchises.map((franchise) => ({
      url: `${SITE_URL}/franchises/${franchise.slug}`,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
    ...characters.map((character) => ({
      url: `${SITE_URL}/characters/${character.slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.4,
    })),
  ];
}
