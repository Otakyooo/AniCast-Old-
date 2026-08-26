import type { CatalogItem } from "./api";

/** Fewer votes than this read as noise rather than a trustworthy average. */
export const MIN_RATING_VOTES = 3;

export interface TitleRatingBadge {
  /** One-decimal average, ready for display. */
  average: string;
  count: number;
}

/**
 * Community score of a title, shown only when real votes back it up.
 * Titles without the annotated aggregates (or below the vote threshold)
 * render no badge instead of an empty placeholder.
 */
export function titleRating(
  item: Pick<CatalogItem, "rating_average" | "rating_count">
): TitleRatingBadge | null {
  if (typeof item.rating_average !== "number") return null;
  const count = item.rating_count ?? 0;
  if (count < MIN_RATING_VOTES) return null;
  return { average: item.rating_average.toFixed(1), count };
}
