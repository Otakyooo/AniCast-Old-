import type { CatalogItem } from "./api";

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
