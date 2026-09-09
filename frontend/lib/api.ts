import { internalApiHeaders } from "./internal-api";

export type CatalogStatus = "ongoing" | "finished" | "planned" | string;

export interface Genre {
  name: string;
  slug: string;
}

export interface Source {
  id: number;
  name: string;
  kind: string;
  provider_name?: string;
  provider_variant_id?: string | null;
  selection_key: string;
  availability: "available" | "unavailable" | "geo_blocked" | "expired" | "provider_error" | string;
  availability_reason?: string;
  is_available: boolean;
  playback_available: boolean;
  playback_mode?: PlaybackMode | null;
}

export type PlaybackMode = "external_link" | "iframe_embed";

export interface PlaybackResponse {
  mode: PlaybackMode;
  url: string;
  expires_at: string;
}

export interface Episode {
  id: number;
  number: number;
  name: string;
  synopsis?: string;
  air_date?: string | null;
  /** Confirmed broadcast moment (ISO 8601 with offset) or null when only the day is known. */
  air_at?: string | null;
  sources?: Source[];
}

export interface EpisodeDetail extends Episode {
  title: Pick<CatalogItem, "name" | "slug" | "title_type" | "status"> & { poster_url?: string };
}

export interface WatchSourceGroup {
  key: string;
  legacy_key?: string | null;
  provider_variant_id?: string | null;
  name: string;
  kind: string;
  provider_name: string;
  episodes_count: number;
  episode_numbers: number[];
  popularity_percent: number;
}

export interface WatchNavigation {
  /** All real Episode rows, including future or metadata-only entries. */
  catalog_episode_numbers?: number[];
  /** Union of episodes with at least one currently authorized player. */
  playable_episode_numbers?: number[];
  /** Compatibility alias for playable_episode_numbers. */
  episode_numbers: number[];
  source_groups: WatchSourceGroup[];
}

export type CharacterRole = "protagonist" | "supporting" | "antagonist" | "cameo" | string;

export interface TitleCastEntry {
  role: CharacterRole;
  sort_order: number;
  character: { name: string; slug: string; original_name: string; image_url: string };
}

export interface TitleCreditEntry {
  role: "director" | "producer" | "writer" | "composer" | "designer" | string;
  role_label: string;
  sort_order: number;
  creator: { name: string; slug: string; image_url: string };
}

export interface CatalogItem {
  id?: number | string;
  slug: string;
  name: string;
  poster_url?: string | null;
  original_name?: string | null;
  localized_names?: Partial<Record<"ru" | "en" | "ja", string>>;
  synopsis?: string | null;
  status?: CatalogStatus | null;
  year?: number | null;
  title_type?: string | null;
  genres?: Genre[];
  franchise?: { name: string; slug: string; description?: string } | null;
  episodes?: Episode[];
  episodes_count?: number;
  characters?: TitleCastEntry[];
  characters_count?: number;
  credits?: TitleCreditEntry[];
  related_titles?: CatalogItem[];
  duration_minutes?: number | null;
  rating_average?: number | null;
  rating_count?: number | null;
}

export interface CatalogResponse {
  count: number;
  results: CatalogItem[];
  next?: string | null;
  previous?: string | null;
}

export type CatalogOrdering = "popular" | "recent" | "name";

export interface CatalogFilters {
  q?: string;
  type?: string;
  status?: string;
  genre?: string;
  page?: number;
  pageSize?: number;
  ordering?: CatalogOrdering;
}

export interface ScheduleItem {
  id: number;
  number: number;
  name: string;
  synopsis?: string;
  air_date: string;
  air_at?: string | null;
  title: Pick<CatalogItem, "name" | "slug" | "title_type" | "status" | "year"> & { poster_url?: string };
}

export interface ScheduleResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ScheduleItem[];
}

export interface FranchiseSummary { name: string; slug: string; description: string; title_count: number; poster_urls: string[]; year_from: number | null; year_to: number | null }
export interface FranchiseDetail extends FranchiseSummary { titles: CatalogItem[] }
export interface FranchiseResponse { count: number; next: string | null; previous: string | null; results: FranchiseSummary[] }

export interface CharacterSummary { name: string; slug: string; original_name: string; description: string; image_url: string; title_count: number }
export interface CharacterDetail extends CharacterSummary { title_links: Array<{ title: CatalogItem; role: string; sort_order: number }> }
export interface CharacterResponse { count: number; next: string | null; previous: string | null; results: CharacterSummary[] }
export interface CreatorDetail { name: string; slug: string; image_url: string; title_credits: Array<{ role: string; role_label: string; sort_order: number; title: CatalogItem }> }

export interface GlobalSearchResponse {
  query: string;
  titles: CatalogItem[];
  characters: CharacterSummary[];
  franchises: FranchiseSummary[];
}
export interface MediaAsset { id: number; kind: string; url: string; thumbnail_url: string; caption: string; credit: string; title: Pick<CatalogItem, "name" | "slug" | "status" | "title_type"> | null; character: CharacterSummary | null }
export interface MediaResponse { count: number; next: string | null; previous: string | null; results: MediaAsset[] }

/** Approved review as published by the community endpoints. */
export interface PublicReview {
  id: number;
  title: { name: string; slug: string };
  author_name: string;
  author_public_id: string | null;
  body: string;
  contains_spoilers: boolean;
  published_at: string | null;
  updated_at: string;
}
export interface PublicReviewsResponse { count: number; next: string | null; previous: string | null; results: PublicReview[] }

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";
// Server-side renders reach the backend directly across the private tunnel
// instead of looping through the public edge (VPS -> internet -> Caddy ->
// tunnel). Plain runtime variable, not NEXT_PUBLIC_*, so the internal origin
// never reaches the client bundle.
const INTERNAL_API_BASE_URL = process.env.INTERNAL_API_BASE_URL ?? "";

function apiBase(): { url: string; internal: boolean } {
  if (INTERNAL_API_BASE_URL && typeof window === "undefined") {
    return { url: INTERNAL_API_BASE_URL, internal: true };
  }
  return { url: API_BASE_URL, internal: false };
}

export function emptyPage<T>(): { count: number; next: string | null; previous: string | null; results: T[] } {
  return { count: 0, next: null, previous: null, results: [] };
}

export function apiErrorStatus(error: unknown): number | undefined {
  return error instanceof Error && Object.hasOwn(error, "status")
    ? (error as Error & { status?: number }).status
    : undefined;
}

async function contentLanguage() {
  if (typeof window !== "undefined") {
    return document.cookie.match(/(?:^|; )anicast_lang=([^;]+)/)?.[1] ?? "ru";
  }
  try {
    const { cookies } = await import("next/headers");
    return (await cookies()).get("anicast_lang")?.value ?? "ru";
  } catch {
    return "ru";
  }
}

const REQUEST_TIMEOUT_MS = 10_000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const language = await contentLanguage();
  const separator = path.includes("?") ? "&" : "?";
  // A stalled backend must fail fast so SSR falls back to the unavailable
  // state instead of hanging the render indefinitely.
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const signal = init?.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
  const base = apiBase();
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Accept-Language": language,
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (base.internal) {
    // The tunnel hop is plain HTTP inside the encrypted AWG link — the same
    // trust domain as Caddy's upstream leg. The header marks it secure for
    // SECURE_SSL_REDIRECT / SECURE_PROXY_SSL_HEADER without touching settings.
    Object.assign(headers, internalApiHeaders());
  }
  const response = await fetch(`${base.url}${path}${separator}lang=${encodeURIComponent(language)}`, {
    ...init,
    headers,
    signal,
  });

  if (!response.ok) {
    const error = new Error(`API request failed with status ${response.status}`);
    Object.assign(error, { status: response.status });
    throw error;
  }

  return response.json() as Promise<T>;
}

/** Fetch options for hot public payloads that tolerate short staleness. */
function revalidated(seconds: number): RequestInit {
  return { next: { revalidate: seconds } };
}

function normalizeCatalog(payload: CatalogResponse | CatalogItem[]): CatalogResponse {
  if (Array.isArray(payload)) {
    return { count: payload.length, results: payload };
  }
  return { ...payload, results: payload.results ?? [] };
}

export async function getCatalog(filters: CatalogFilters = {}, signal?: AbortSignal): Promise<CatalogResponse> {
  const query = new URLSearchParams();
  if (filters.q?.trim()) query.set("q", filters.q.trim());
  if (filters.type) query.set("type", filters.type);
  if (filters.status) query.set("status", filters.status);
  if (filters.genre) query.set("genre", filters.genre);
  if (filters.ordering) query.set("ordering", filters.ordering);
  if (filters.page && filters.page > 1) query.set("page", String(filters.page));
  if (filters.pageSize) query.set("page_size", String(filters.pageSize));
  const suffix = query.size ? `?${query.toString()}` : "";
  const payload = await request<CatalogResponse | CatalogItem[]>(`/titles/${suffix}`, { ...revalidated(60), signal });
  return normalizeCatalog(payload);
}

export interface GenreOption { slug: string; name: string; titles_count: number }

/** Localized genre options for the catalog filter bar, most used first. */
export async function getGenres(): Promise<GenreOption[]> {
  return request<GenreOption[]>("/genres/", revalidated(300));
}

export async function getCatalogItemEpisodes(
  slug: string,
  page = 1,
  pageSize = 20,
  charactersPage = 1,
  charactersPageSize = 8,
): Promise<CatalogItem> {
  const query = new URLSearchParams({
    episodes_page: String(page),
    episodes_page_size: String(pageSize),
    characters_page: String(charactersPage),
    characters_page_size: String(charactersPageSize),
    episode_sources: "0",
  });
  const path = `/titles/${encodeURIComponent(slug)}/?${query}`;
  try {
    // Detail pages are dynamic and should never inherit a cached transient API
    // failure. A single retry absorbs a tunnel reconnect without replacing the
    // complete title screen with the generic unavailable state.
    return await request<CatalogItem>(path, { cache: "no-store" });
  } catch (error) {
    const status = apiErrorStatus(error);
    if (status !== undefined) throw error;
    return request<CatalogItem>(path, { cache: "no-store" });
  }
}

/** Small cacheable title payload used only for metadata and first-episode links. */
export async function getCatalogItemMetadata(slug: string): Promise<CatalogItem> {
  const query = new URLSearchParams({
    episodes_page: "1",
    episodes_page_size: "1",
    characters_page: "1",
    characters_page_size: "1",
    episode_sources: "0",
  });
  return request<CatalogItem>(`/titles/${encodeURIComponent(slug)}/?${query}`, revalidated(60));
}

/**
 * Lowest existing episode number of a title, or null when it has none.
 *
 * Used by the title hero, whose watch action must not depend on which episode
 * page is currently displayed.
 */
export async function getFirstEpisodeNumber(slug: string): Promise<number | null> {
  try {
    const item = await getCatalogItemMetadata(slug);
    return item.episodes?.[0]?.number ?? null;
  } catch {
    return null;
  }
}

export async function getEpisode(slug: string, number: number): Promise<EpisodeDetail> {
  return request<EpisodeDetail>(`/titles/${encodeURIComponent(slug)}/episodes/${number}/`, { cache: "no-store" });
}

/** Server- and client-callable episode metadata for a number window.
 *
 * The player rail lazily enriches its number-only rows (names, air dates)
 * with this slice; the window is bounded by the backend, so a long series
 * never serializes whole. Returns an empty array when the slice is empty.
 */
export async function getEpisodeRange(
  slug: string,
  from: number,
  to: number,
  signal?: AbortSignal,
): Promise<Episode[]> {
  const query = new URLSearchParams({
    episodes_from: String(from),
    episodes_to: String(to),
    episodes_page_size: "50",
    episode_sources: "0",
    characters_page: "1",
    characters_page_size: "1",
  });
  const path = `/titles/${encodeURIComponent(slug)}/?${query}`;
  const collected: Episode[] = [];
  for (let page = 1; page <= 20; page += 1) {
    const suffix = page === 1 ? "" : `&episodes_page=${page}`;
    const item = await request<CatalogItem>(`${path}${suffix}`, { cache: "no-store", signal });
    const rows = item.episodes ?? [];
    collected.push(...rows);
    // Numbering gaps mean the window can hold fewer rows than its span, so
    // the stop condition is the page content itself: a short page is the
    // queryset end (paging further would 404), and the last row reaching
    // `to` means the window is covered.
    if (rows.length < 50 || rows[rows.length - 1].number >= to) break;
  }
  return collected;
}

export async function getWatchNavigation(slug: string): Promise<WatchNavigation> {
  return request<WatchNavigation>(`/titles/${encodeURIComponent(slug)}/watch-navigation/`, revalidated(60));
}

export async function getSimilarTitles(slug: string): Promise<CatalogItem[]> {
  try {
    return await request<CatalogItem[]>(`/titles/${encodeURIComponent(slug)}/similar/`, revalidated(300));
  } catch {
    return [];
  }
}

export async function getSchedule(from: string, to: string): Promise<ScheduleResponse> {
  const query = new URLSearchParams({ from, to, page_size: "200" });
  return request<ScheduleResponse>(`/schedule/?${query}`, revalidated(60));
}

/** Minimum length accepted by the backend search endpoint. */
export const SEARCH_MIN_LENGTH = 2;

export async function globalSearch(query: string, signal?: AbortSignal): Promise<GlobalSearchResponse> {
  return request<GlobalSearchResponse>(`/search/?q=${encodeURIComponent(query)}`, { cache: "no-store", signal });
}

export async function getFranchises(page = 1, search = "", pageSize?: number): Promise<FranchiseResponse> {
  const query = new URLSearchParams();
  if (search.trim()) query.set("q", search.trim());
  if (page > 1) query.set("page", String(page));
  if (pageSize) query.set("page_size", String(pageSize));
  const suffix = query.size ? `?${query.toString()}` : "";
  return request<FranchiseResponse>(`/franchises/${suffix}`, revalidated(300));
}

export async function getFranchise(slug: string): Promise<FranchiseDetail> {
  return request<FranchiseDetail>(`/franchises/${encodeURIComponent(slug)}/`, revalidated(300));
}

export async function getCharacters(search = "", page = 1, pageSize?: number): Promise<CharacterResponse> {
  const query = new URLSearchParams();
  if (search.trim()) query.set("q", search.trim());
  if (page > 1) query.set("page", String(page));
  if (pageSize) query.set("page_size", String(pageSize));
  return request<CharacterResponse>(`/characters/${query.size ? `?${query}` : ""}`, revalidated(300));
}

export async function getCharacter(slug: string): Promise<CharacterDetail> {
  return request<CharacterDetail>(`/characters/${encodeURIComponent(slug)}/`, revalidated(300));
}

export async function getCreator(slug: string): Promise<CreatorDetail> {
  return request<CreatorDetail>(`/creators/${encodeURIComponent(slug)}/`, revalidated(300));
}

/**
 * Approved public reviews, fetchable during SSR.
 *
 * `lib/community.ts` has a browser-only version built on a relative URL. This one
 * goes through `request()`, so it also works on the server: the community feed is
 * public content and has to exist in the HTML, both for crawlers and because it
 * is the only page that links to public profiles and collections.
 */
export async function getPublicReviewsPage(page = 1, pageSize = 20): Promise<PublicReviewsResponse> {
  const query = new URLSearchParams({ page_size: String(pageSize) });
  if (page > 1) query.set("page", String(page));
  return request<PublicReviewsResponse>(`/community/reviews/?${query}`, revalidated(60));
}

export async function getMedia(kind = ""): Promise<MediaResponse> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return request<MediaResponse>(`/media/${query}`, revalidated(300));
}

export async function getPlayback(sourceId: number, signal?: AbortSignal): Promise<PlaybackResponse> {
  return request<PlaybackResponse>(`/sources/${sourceId}/playback/`, { cache: "no-store", signal });
}
