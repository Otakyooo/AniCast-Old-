import type { CatalogItem } from "./api.ts";
import { addDays } from "./schedule.ts";

/**
 * Home shelves are filled from independent catalog queries (ongoing/popular,
 * popular/newest), so the same title can appear in both. A repeated card on
 * one screen looks like a data bug, so the second shelf keeps only titles the
 * lead shelf did not take, preserving its own ordering.
 */
export function dedupeShelf<T extends { slug: string }>(lead: T[], follower: T[]): T[] {
  const seen = new Set(lead.map((item) => item.slug));
  return follower.filter((item) => !seen.has(item.slug));
}

/** Fewer cards than this cannot fill a poster rail row. */
export const RECENT_SHELF_MIN_DENSE = 4;
/** Days the shelf calls "this week" before it has to admit a wider window. */
export const RECENT_SHELF_WEEK_DAYS = 7;

export interface RecentShelfPlan<T> {
  items: T[];
  /** The week alone was too thin, so older releases fill the shelf. */
  widened: boolean;
  /** Too few releases exist at all: render compact rows, not a poster rail. */
  compact: boolean;
}

/**
 * Decide what the "recently released" shelf shows.
 *
 * The rail reserves a poster-height row sized for six cards, so one lone
 * episode left most of the block empty. The shelf therefore takes releases
 * from a wider window when the last week is thin, and drops to a compact
 * layout when even that cannot fill a row — an honest small block instead of
 * a hole. `items` must already be ordered newest first by the API.
 */
export function planRecentEpisodeShelf<T extends { air_date?: string | null }>(
  items: T[],
  todayKey: string,
  minDense = RECENT_SHELF_MIN_DENSE,
): RecentShelfPlan<T> {
  const weekStart = addDays(todayKey, -(RECENT_SHELF_WEEK_DAYS - 1));
  const weekItems = items.filter((item) => (item.air_date ?? "").slice(0, 10) >= weekStart);
  if (weekItems.length >= minDense) {
    return { items: weekItems, widened: false, compact: false };
  }
  return {
    items,
    widened: items.length > weekItems.length,
    compact: items.length < minDense,
  };
}
