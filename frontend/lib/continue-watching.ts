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
  /** Playback position inside `resume_episode`; 0 when it was never started. */
  resume_at_seconds?: number;
  /** Duration of `resume_episode`, absent while an older API is live. */
  duration_seconds?: number | null;
  progress_percent?: number;
  /** Voice-over snapshot of what the viewer actually played. */
  source_selection_key?: string;
  source_name?: string;
  source_kind?: string;
  /** The next part of the franchise, for the "next part of your story" hint. */
  franchise_next?: {
    name: string;
    slug: string;
    poster_url?: string | null;
    year?: number | null;
  } | null;
  last_opened_at: string;
}

/**
 * Shelf progress in percent. Prefers the real playback position inside the
 * resume episode and falls back to the share of watched episodes, so a card
 * never claims progress the backend did not confirm.
 */
export function resumeProgressPercent(entry: ContinueWatchingEntry): number {
  const position = entry.resume_at_seconds;
  const duration = entry.duration_seconds;
  if (typeof position === "number" && typeof duration === "number" && duration > 0) {
    return Math.min(100, Math.max(0, Math.round((position / duration) * 100)));
  }
  const total = entry.title.episodes_count;
  if (typeof total === "number" && total > 0) {
    return Math.min(100, Math.max(0, Math.round((entry.watched_count / total) * 100)));
  }
  return 0;
}

export function resumeEpisode(entry: ContinueWatchingEntry): Episode | null {
  return entry.resume_episode ?? entry.next_episode;
}

/** duration - position, clamped at zero; 0 when the runtime is unknown. */
export function remainingSeconds(entry: ContinueWatchingEntry): number {
  const duration = typeof entry.duration_seconds === "number" ? entry.duration_seconds : 0;
  if (duration <= 0) return 0;
  return Math.max(0, duration - (entry.resume_at_seconds ?? 0));
}

/** "Осталось 9 мин" -- one representation only, never the raw timestamp or a
 *  percentage next to it. Rounded to whole minutes, per the spec. */
export function formatRemaining(
  seconds: number,
  t: (key: string, values?: Record<string, string | number>) => string,
): string {
  if (seconds <= 0) return "";
  if (seconds < 60) return t("home.remainingUnderMinute");
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return t("home.remainingMinutes", { count: minutes });
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0
    ? t("home.remainingHoursMinutes", { hours, minutes: 0 })
    : t("home.remainingHoursMinutes", { hours, minutes: rest });
}

/** Resets the saved position of one episode to 0:00. The card stays in the
 *  shelf; only the playback position is cleared. */
export async function resetEpisodeProgress(slug: string, number: number, durationSeconds: number) {
  const { syncEpisodeProgress } = await import("./history");
  await syncEpisodeProgress(slug, number, {
    watched_seconds: 0,
    // The write serializer requires a positive duration; fall back to a second
    // so a title with an unknown runtime can still be reset.
    duration_seconds: durationSeconds > 0 ? Math.round(durationSeconds) : 1,
    event: "progress",
  });
}

/**
 * True when the episode the shelf would resume was actually started.
 *
 * The backend reports a playback position only for the episode the viewer
 * opened; a resume target further ahead (the next unwatched episode) reports
 * zero. Both the label and the progress bar key off this, so a title queued for
 * its next episode never claims progress it does not have.
 */
export function resumeEpisodeStarted(entry: ContinueWatchingEntry): boolean {
  return (entry.resume_at_seconds ?? 0) > 0;
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

async function mutateHidden(slug: string, method: "POST" | "DELETE") {
  const { getCsrfToken } = await import("./auth");
  const csrf = await getCsrfToken();
  const response = await fetch(`/api/v1/continue-watching/${encodeURIComponent(slug)}/hide/`, {
    method,
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrf },
  });
  if (!response.ok) throw new ContinueWatchingApiError(response.status);
}

/** Removes a title from the resume shelf only; history stays intact. */
export function hideFromContinueWatching(slug: string) {
  return mutateHidden(slug, "POST");
}

/** Restores a title that was removed from the resume shelf. */
export function unhideFromContinueWatching(slug: string) {
  return mutateHidden(slug, "DELETE");
}
