import type { CatalogItem } from "./api";
import { getCsrfToken } from "./auth";

export type LibraryStatus = "planned" | "watching" | "completed" | "on_hold" | "dropped";

export interface LibraryEntry {
  title: CatalogItem;
  status: LibraryStatus;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface LibraryResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: LibraryEntry[];
}

export class LibraryApiError extends Error {
  constructor(public status: number, message = "Не удалось выполнить запрос к библиотеке.") {
    super(message);
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) throw new LibraryApiError(response.status);
  return response.json() as Promise<T>;
}

export async function getLibrary(filters: { status?: string; favorite?: boolean; page?: number } = {}, signal?: AbortSignal) {
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.favorite) query.set("favorite", "true");
  if (filters.page && filters.page > 1) query.set("page", String(filters.page));
  return parseResponse<LibraryResponse>(await fetch(`/api/v1/library/?${query}`, { credentials: "same-origin", cache: "no-store", signal }));
}

export async function getLibraryEntry(slug: string, signal?: AbortSignal) {
  const response = await fetch(`/api/v1/library/${encodeURIComponent(slug)}/`, { credentials: "same-origin", cache: "no-store", signal });
  if (response.status === 404) return null;
  return parseResponse<LibraryEntry>(response);
}

export async function putLibraryEntry(slug: string, payload: { status: LibraryStatus; is_favorite: boolean }) {
  const csrf = await getCsrfToken();
  return parseResponse<LibraryEntry>(await fetch(`/api/v1/library/${encodeURIComponent(slug)}/`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: JSON.stringify(payload),
  }));
}

export async function deleteLibraryEntry(slug: string) {
  const csrf = await getCsrfToken();
  const response = await fetch(`/api/v1/library/${encodeURIComponent(slug)}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrf },
  });
  if (!response.ok) throw new LibraryApiError(response.status);
}
