import type { AccountSummary } from "./auth.ts";

export const RECENT_NOTES_LIMIT = 3;

export function libraryTotalCount(library: AccountSummary["library"]): number {
  return Object.values(library).reduce((sum, value) => sum + value, 0);
}

export function pickRecentNotes<T>(results: T[]): T[] {
  return results.slice(0, RECENT_NOTES_LIMIT);
}

export function summaryWith(partial: Partial<AccountSummary>): AccountSummary {
  return {
    library: { planned: 0, watching: 0, completed: 0, on_hold: 0, dropped: 0 },
    favorites: 0,
    watched_episodes: 0,
    watched_hours: 0,
    average_rating: null,
    top_genres: [],
    notes: 0,
    collections: 0,
    ratings: 0,
    reviews: 0,
    activity: [],
    ...partial,
  };
}
