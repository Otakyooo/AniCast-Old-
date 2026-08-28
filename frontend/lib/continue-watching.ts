import type { CatalogItem, Episode } from "./api";

/** One resume shelf entry: the last opened episode of a title and, when it
 *  exists, the episode the viewer should continue with. */
export interface ContinueWatchingEntry {
  title: CatalogItem;
  last_episode: Episode;
  resume_episode?: Episode | null;
  /** Compatibility field for one older backend release. */
  next_episode: Episode | null;
  is_watched: boolean;
  watched_count: number;
  last_opened_at: string;
}

export function resumeEpisode(entry: ContinueWatchingEntry): Episode | null {
  return entry.resume_episode ?? entry.next_episode;
}

export class ContinueWatchingApiError extends Error {
  status: number;

  constructor(status: number) {
    super(`Continue watching request failed with status ${status}`);
    this.status = status;
  }
}

/** Returns null for guests so callers can hide the shelf instead of erroring. */
export async function getContinueWatching(signal?: AbortSignal): Promise<ContinueWatchingEntry[] | null> {
  const response = await fetch("/api/v1/continue-watching/", {
    credentials: "same-origin",
    cache: "no-store",
    signal,
  });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new ContinueWatchingApiError(response.status);
  return response.json() as Promise<ContinueWatchingEntry[]>;
}
