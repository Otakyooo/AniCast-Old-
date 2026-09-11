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
/** Days the shelf actually promises, days the window never crosses. */
export const RECENT_SHELF_WEEK_DAYS = 7;

export interface RecentShelfPlan<T> {
  items: T[];
  /** Too few fresh releases for the rail: compact rows instead. */
  compact: boolean;
}

/** One group of episodes of the same title inside the recent-week shelf. */
export interface RecentTitleGroup<T> {
  slug: string;
  latest: T;
  extraCount: number;
  latestAirDate: string;
}

/**
 * Strict weekly window and grouping by title: a shelf titled "Новые серии"
 * never shows releases older than the promised week. Several episodes of one
 * title inside that week merge into one card with a "+N" extra count.
 */
export function planRecentEpisodeShelf<T extends {
  air_date?: string | null;
  air_at?: string | null;
  title: { slug: string };
}>(items: T[], todayKey: string, minDense = RECENT_SHELF_MIN_DENSE): RecentShelfPlan<T> {
  const weekStart = addDays(todayKey, -(RECENT_SHELF_WEEK_DAYS - 1));
  const inWindow = items.filter((item) => (item.air_date ?? "").slice(0, 10) >= weekStart);
  return {
    items: inWindow,
    compact: inWindow.length < minDense,
  };
}

export function groupRecentEpisodesByTitle<T extends {
  air_date?: string | null;
  title: { slug: string };
}>(items: T[]): RecentTitleGroup<T>[] {
  const byTitle = new Map<string, RecentTitleGroup<T>>();
  for (const item of items) {
    const existing = byTitle.get(item.title.slug);
    if (!existing) {
      byTitle.set(item.title.slug, {
        slug: item.title.slug,
        latest: item,
        extraCount: 0,
        latestAirDate: item.air_date ?? "",
      });
      continue;
    }
    existing.extraCount += 1;
    // The API orders newest first, so the first seen is the newest episode;
    // the date kept is still the newest air date in the group.
    if ((item.air_date ?? "") > existing.latestAirDate) existing.latestAirDate = item.air_date ?? "";
  }
  return [...byTitle.values()];
}
