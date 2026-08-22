export type CatalogStatus = "ongoing" | "finished" | "planned" | string;

export interface Genre {
  name: string;
  slug: string;
}

export interface Source {
  id: number;
  name: string;
  kind: string;
  availability: "available" | "unavailable" | "geo_blocked" | "expired" | "provider_error" | string;
  availability_reason?: string;
  is_available: boolean;
  playback_available: boolean;
}

export interface PlaybackResponse {
  mode: "external_link";
  url: string;
  expires_at: string;
}

export interface Episode {
  id: number;
  number: number;
  name: string;
  synopsis?: string;
  air_date?: string | null;
  sources?: Source[];
}

export interface CatalogItem {
  id?: number | string;
  slug: string;
  name: string;
  original_name?: string | null;
  synopsis?: string | null;
  status?: CatalogStatus | null;
  year?: number | null;
  title_type?: string | null;
  genres?: Genre[];
  franchise?: { name: string; slug: string; description?: string } | null;
  episodes?: Episode[];
}

export interface CatalogResponse {
  count: number;
  results: CatalogItem[];
  next?: string | null;
  previous?: string | null;
}

export interface CatalogFilters {
  q?: string;
  type?: string;
  status?: string;
  genre?: string;
  page?: number;
  pageSize?: number;
}

export interface ScheduleItem {
  id: number;
  number: number;
  name: string;
  synopsis?: string;
  air_date: string;
  title: Pick<CatalogItem, "name" | "slug" | "title_type" | "status"> & { poster_url?: string };
}

export interface ScheduleResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ScheduleItem[];
}

export interface FranchiseSummary { name: string; slug: string; description: string; title_count: number }
export interface FranchiseDetail extends FranchiseSummary { titles: CatalogItem[] }
export interface FranchiseResponse { count: number; next: string | null; previous: string | null; results: FranchiseSummary[] }

export interface CharacterSummary { name: string; slug: string; original_name: string; description: string; image_url: string; title_count: number }
export interface CharacterDetail extends CharacterSummary { title_links: Array<{ title: CatalogItem; role: string; sort_order: number }> }
export interface CharacterResponse { count: number; next: string | null; previous: string | null; results: CharacterSummary[] }
export interface MediaAsset { id: number; kind: string; url: string; thumbnail_url: string; caption: string; credit: string; title: Pick<CatalogItem, "name" | "slug" | "status" | "title_type"> | null; character: CharacterSummary | null }
export interface MediaResponse { count: number; next: string | null; previous: string | null; results: MediaAsset[] }

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const language = await contentLanguage();
  const separator = path.includes("?") ? "&" : "?";
  const response = await fetch(`${API_BASE_URL}${path}${separator}lang=${encodeURIComponent(language)}`, {
    ...init,
    headers: { Accept: "application/json", "Accept-Language": language, ...init?.headers },
  });

  if (!response.ok) {
    const error = new Error(`API request failed with status ${response.status}`);
    Object.assign(error, { status: response.status });
    throw error;
  }

  return response.json() as Promise<T>;
}

function normalizeCatalog(payload: CatalogResponse | CatalogItem[]): CatalogResponse {
  if (Array.isArray(payload)) {
    return { count: payload.length, results: payload };
  }
  return { ...payload, results: payload.results ?? [] };
}

export async function getCatalog(filters: CatalogFilters = {}): Promise<CatalogResponse> {
  const query = new URLSearchParams();
  if (filters.q?.trim()) query.set("q", filters.q.trim());
  if (filters.type) query.set("type", filters.type);
  if (filters.status) query.set("status", filters.status);
  if (filters.genre) query.set("genre", filters.genre);
  if (filters.page && filters.page > 1) query.set("page", String(filters.page));
  if (filters.pageSize) query.set("page_size", String(filters.pageSize));
  const suffix = query.size ? `?${query.toString()}` : "";
  const payload = await request<CatalogResponse | CatalogItem[]>(`/titles/${suffix}`, { cache: "no-store" });
  return normalizeCatalog(payload);
}

export async function getCatalogItem(slug: string): Promise<CatalogItem> {
  return request<CatalogItem>(`/titles/${encodeURIComponent(slug)}/`, { cache: "no-store" });
}

export async function getSimilarTitles(slug: string): Promise<CatalogItem[]> {
  try {
    return await request<CatalogItem[]>(`/titles/${encodeURIComponent(slug)}/similar/`);
  } catch {
    return [];
  }
}

export async function getSchedule(from: string, to: string): Promise<ScheduleResponse> {
  const query = new URLSearchParams({ from, to, page_size: "200" });
  return request<ScheduleResponse>(`/schedule/?${query}`, { cache: "no-store" });
}

export async function getFranchises(page = 1): Promise<FranchiseResponse> {
  return request<FranchiseResponse>(`/franchises/${page > 1 ? `?page=${page}` : ""}`, { cache: "no-store" });
}

export async function getFranchise(slug: string): Promise<FranchiseDetail> {
  return request<FranchiseDetail>(`/franchises/${encodeURIComponent(slug)}/`, { cache: "no-store" });
}

export async function getCharacters(search = ""): Promise<CharacterResponse> {
  const query = search ? `?q=${encodeURIComponent(search)}` : "";
  return request<CharacterResponse>(`/characters/${query}`, { cache: "no-store" });
}

export async function getCharacter(slug: string): Promise<CharacterDetail> {
  return request<CharacterDetail>(`/characters/${encodeURIComponent(slug)}/`, { cache: "no-store" });
}

export async function getMedia(kind = ""): Promise<MediaResponse> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return request<MediaResponse>(`/media/${query}`, { cache: "no-store" });
}

export async function getPlayback(sourceId: number): Promise<PlaybackResponse> {
  return request<PlaybackResponse>(`/sources/${sourceId}/playback/`, { cache: "no-store" });
}
