export type CatalogStatus = "ongoing" | "finished" | "planned" | string;

export interface Genre {
  name: string;
  slug: string;
}

export interface Source {
  name: string;
  kind: string;
  url: string;
  availability: "available" | "unavailable" | "geo_blocked" | "expired" | "provider_error" | string;
  availability_reason?: string;
  is_available: boolean;
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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
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
