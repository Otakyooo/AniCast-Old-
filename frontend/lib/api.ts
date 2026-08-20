export type CatalogStatus = "ongoing" | "completed" | "upcoming" | string;

export interface CatalogItem {
  id: number | string;
  slug: string;
  title: string;
  original_title?: string | null;
  description?: string | null;
  status?: CatalogStatus | null;
  year?: number | null;
  episodes?: number | null;
  genres?: string[];
  studios?: string[];
  type?: string | null;
  rating?: number | null;
  accent?: string | null;
}

export interface CatalogResponse {
  count: number;
  results: CatalogItem[];
  next?: string | null;
  previous?: string | null;
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

export async function getCatalog(search?: string): Promise<CatalogResponse> {
  const query = search?.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  const payload = await request<CatalogResponse | CatalogItem[]>(`/titles/${query}`, { cache: "no-store" });
  return normalizeCatalog(payload);
}

export async function getCatalogItem(slug: string): Promise<CatalogItem> {
  return request<CatalogItem>(`/titles/${encodeURIComponent(slug)}/`, { cache: "no-store" });
}
