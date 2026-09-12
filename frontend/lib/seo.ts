import type { CatalogFilters } from "./api.ts";
import type { Locale } from "../i18n/config.ts";
import { SITE_URL } from "./site.ts";

export const NO_INDEX_ROBOTS = {
  index: false,
  follow: true,
} as const;

function episodeNumber(value: string | number | undefined) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

/** Playback stays on the canonical title page; episode and voice are UI state. */
export function titleWatchHref(slug: string, episode: string | number = 1, voice?: string) {
  const query = new URLSearchParams({ episode: String(episodeNumber(episode)) });
  const normalizedVoice = voice?.trim();
  if (normalizedVoice) query.set("voice", normalizedVoice);
  return `/titles/${encodeURIComponent(slug)}?${query}#watch`;
}

/**
 * Search, sorting and facet combinations are useful UI states, but weak
 * landing pages. Only the base catalog and its real pagination are indexable.
 */
export function catalogSeoState(filters: CatalogFilters, pageExists = true) {
  const hasFacet = Boolean(
    filters.q?.trim()
    || filters.type
    || filters.status
    || filters.genre
    || filters.ordering
    || (filters.seasons && filters.seasons !== "grouped"),
  );
  const page = Number.isInteger(filters.page) && (filters.page ?? 1) > 1
    ? filters.page ?? 1
    : 1;

  return {
    canonical: hasFacet || !pageExists || page === 1 ? "/catalog" : `/catalog?page=${page}`,
    index: !hasFacet && pageExists,
  };
}

export function catalogPageExists(total: number, page: number, pageSize = 20) {
  if (page <= 1) return true;
  return page <= Math.max(1, Math.ceil(Math.max(total, 0) / pageSize));
}

/**
 * Franchise index: same reasoning as the catalog, one facet instead of five.
 *
 * A franchise search result page is a weak landing page and a duplicate of the
 * index, so `?q=` consolidates onto `/franchises`. Real pagination stays
 * self-canonical and indexable; a page past the last result does not.
 */
export function franchiseSeoState(
  { query, page = 1 }: { query?: string; page?: number },
  pageExists = true,
) {
  const hasQuery = Boolean(query?.trim());
  const resolvedPage = Number.isInteger(page) && page > 1 ? page : 1;
  return {
    canonical:
      hasQuery || !pageExists || resolvedPage === 1
        ? "/franchises"
        : `/franchises?page=${resolvedPage}`,
    index: !hasQuery && pageExists,
  };
}

/**
 * Community review index: real pagination is self-canonical and indexable, a
 * page past the last review is not. No facets exist on this page.
 */
export function communitySeoState(page = 1, pageExists = true) {
  const resolvedPage = Number.isInteger(page) && page > 1 ? page : 1;
  return {
    canonical:
      !pageExists || resolvedPage === 1 ? "/community" : `/community?page=${resolvedPage}`,
    index: pageExists,
  };
}

export function titleSchemaType(titleType?: string | null) {
  return titleType === "movie" ? "Movie" : "TVSeries";
}

export function titleOpenGraphType(titleType?: string | null) {
  return titleType === "movie" ? "video.movie" as const : "video.tv_show" as const;
}

export function websiteJsonLd(locale: Locale) {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Anicast",
    alternateName: "АниКаст",
    url: SITE_URL,
    inLanguage: locale,
  };
}

/**
 * Serialize a JSON-LD payload for an inline `<script>`.
 *
 * The values come from an external metadata importer, so a synopsis containing
 * `</script` would otherwise close the element early and turn the rest of the
 * payload into markup. Escaping `<` covers that, and escaping the line and
 * paragraph separators keeps the result valid JavaScript source as well as
 * valid JSON.
 */
export function jsonLdScript(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}
