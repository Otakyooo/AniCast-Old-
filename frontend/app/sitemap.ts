import type { MetadataRoute } from "next";
import { getCatalog, getCharacters, getFranchises } from "../lib/api";
import { SITE_URL } from "../lib/site";

// Sitemap must reflect the live catalog on every request, not the state at
// build time.
export const dynamic = "force-dynamic";

const MAX_PAGES = 25;

interface Paged<T> {
  count: number;
  next?: string | null;
  results: T[];
}

/**
 * Walk a paginated public endpoint until it is exhausted. The loop follows
 * page numbers rather than trusting a specific page size, so it keeps working
 * whatever the backend caps pages at. Any API failure degrades to the entries
 * collected so far — the sitemap still ships with the static routes instead
 * of erroring like the pages do.
 */
async function collectAll<T>(fetchPage: (page: number) => Promise<Paged<T>>): Promise<T[]> {
  const all: T[] = [];
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    let response: Paged<T>;
    try {
      response = await fetchPage(page);
    } catch {
      return all;
    }
    const results = response.results ?? [];
    if (!results.length) return all;
    all.push(...results);
    if (all.length >= Math.max(response.count, 0)) return all;
  }
  return all;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/catalog`, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/schedule`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/franchises`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${SITE_URL}/characters`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${SITE_URL}/media`, changeFrequency: "weekly", priority: 0.4 },
    { url: `${SITE_URL}/community`, changeFrequency: "daily", priority: 0.5 },
  ];

  const [titles, franchises, characters] = await Promise.all([
    collectAll((page) => getCatalog({ page, pageSize: 100 })),
    collectAll((page) => getFranchises(page)),
    collectAll((page) => getCharacters("", page)),
  ]);

  return [
    ...staticRoutes,
    ...titles.map((title) => ({
      url: `${SITE_URL}/titles/${title.slug}`,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    ...franchises.map((franchise) => ({
      url: `${SITE_URL}/franchises/${franchise.slug}`,
      changeFrequency: "weekly" as const,
      priority: 0.5,
    })),
    ...characters.map((character) => ({
      url: `${SITE_URL}/characters/${character.slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.4,
    })),
  ];
}
