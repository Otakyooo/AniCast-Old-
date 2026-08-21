import type { CatalogItem } from "./api";
import { getCsrfToken } from "./auth";

export interface TitleNote { title: CatalogItem; body: string; created_at: string; updated_at: string }
export interface NotesResponse { count: number; next: string | null; previous: string | null; results: TitleNote[] }
export class NoteApiError extends Error { constructor(public status: number) { super("Не удалось выполнить запрос заметки."); } }

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) throw new NoteApiError(response.status);
  return response.json() as Promise<T>;
}

export async function getNotes(signal?: AbortSignal) {
  return parse<NotesResponse>(await fetch("/api/v1/notes/", { credentials: "same-origin", cache: "no-store", signal }));
}

export async function getTitleNote(slug: string, signal?: AbortSignal) {
  const response = await fetch(`/api/v1/notes/${encodeURIComponent(slug)}/`, { credentials: "same-origin", cache: "no-store", signal });
  if (response.status === 404) return null;
  return parse<TitleNote>(response);
}

export async function putTitleNote(slug: string, body: string) {
  const csrf = await getCsrfToken();
  return parse<TitleNote>(await fetch(`/api/v1/notes/${encodeURIComponent(slug)}/`, { method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, body: JSON.stringify({ body }) }));
}

export async function deleteTitleNote(slug: string) {
  const csrf = await getCsrfToken();
  const response = await fetch(`/api/v1/notes/${encodeURIComponent(slug)}/`, { method: "DELETE", credentials: "same-origin", headers: { "X-CSRFToken": csrf } });
  if (!response.ok) throw new NoteApiError(response.status);
}
