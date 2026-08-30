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
    || filters.ordering,
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

export function titleSchemaType(titleType?: string | null) {
  return titleType === "movie" ? "Movie" : "TVSeries";
}

export function websiteJsonLd(locale: Locale) {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "AniCast",
    alternateName: "АниКаст",
    url: SITE_URL,
    inLanguage: locale,
  };
}
