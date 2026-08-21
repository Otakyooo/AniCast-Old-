import type { CatalogItem, Episode } from "./api";
import { getCsrfToken } from "./auth";
import { clientMessage } from "../i18n/client";

export interface EpisodeProgress {
  title: CatalogItem;
  episode: Episode;
  is_watched: boolean;
  last_opened_at: string;
  watched_at: string | null;
}

export interface HistoryResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: EpisodeProgress[];
}

export class HistoryApiError extends Error {
  constructor(public status: number) {
    super(clientMessage("Не удалось выполнить запрос истории.", "History request failed."));
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) throw new HistoryApiError(response.status);
  return response.json() as Promise<T>;
}

export async function getHistory(pageSize = 20, signal?: AbortSignal) {
  return parse<HistoryResponse>(await fetch(`/api/v1/history/?page_size=${pageSize}`, {
    credentials: "same-origin",
    cache: "no-store",
    signal,
  }));
}

async function mutateProgress(slug: string, number: number, init: RequestInit) {
  const csrf = await getCsrfToken();
  return parse<EpisodeProgress>(await fetch(`/api/v1/episodes/${encodeURIComponent(slug)}/${number}/progress/`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, ...init.headers },
  }));
}

export function recordEpisodeOpen(slug: string, number: number) {
  return mutateProgress(slug, number, { method: "POST" });
}

export function setEpisodeWatched(slug: string, number: number, isWatched: boolean) {
  return mutateProgress(slug, number, { method: "PUT", body: JSON.stringify({ is_watched: isWatched }) });
}
