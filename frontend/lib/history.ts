import type { CatalogItem, Episode } from "./api";
import { getCsrfToken } from "./auth";
import { clientMessage } from "../i18n/client";

export interface PlaybackProgressData {
  is_watched: boolean;
  /** Last confirmed playback position. Optional while an older API is live. */
  watched_seconds?: number;
  duration_seconds?: number | null;
  progress_percent?: number;
  last_opened_at: string;
  watched_at: string | null;
}

export interface EpisodeProgress extends PlaybackProgressData {
  title: CatalogItem;
  episode: Episode;
}

export type ProgressSyncEvent = "progress" | "pause" | "ended";

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

let progressCsrfRequest: Promise<string> | null = null;

async function getProgressCsrfToken() {
  if (!progressCsrfRequest) {
    progressCsrfRequest = getCsrfToken().catch((error) => {
      progressCsrfRequest = null;
      throw error;
    });
  }
  return progressCsrfRequest;
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
  const csrf = await getProgressCsrfToken();
  return parse<EpisodeProgress>(await fetch(`/api/v1/episodes/${encodeURIComponent(slug)}/${number}/progress/`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, ...init.headers },
  }));
}

export function recordEpisodeOpen(slug: string, number: number) {
  return mutateProgress(slug, number, { method: "POST" });
}

export function syncEpisodeProgress(
  slug: string,
  number: number,
  payload: {
    watched_seconds: number;
    duration_seconds: number;
    event: ProgressSyncEvent;
  },
  keepalive = false,
) {
  return mutateProgress(slug, number, {
    method: "PATCH",
    body: JSON.stringify(payload),
    keepalive,
  }) as Promise<PlaybackProgressData>;
}

export async function getEpisodeProgress(slug: string, number: number, signal?: AbortSignal) {
  return parse<EpisodeProgress>(await fetch(`/api/v1/episodes/${encodeURIComponent(slug)}/${number}/progress/`, {
    credentials: "same-origin",
    cache: "no-store",
    signal,
  }));
}
