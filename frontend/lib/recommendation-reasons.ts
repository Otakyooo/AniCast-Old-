export interface RecommendationReasons {
  genres: string[];
  franchise: boolean;
}

type Translate = (key: string, values?: Record<string, string | number>) => string;

/**
 * Human-readable reason line for a recommendation card, e.g.
 * "Based on your genres: Drama, Comedy · From your franchise".
 * Returns null when there is nothing honest to say (missing reasons payload).
 */
export function recommendationReasonText(
  reasons: RecommendationReasons | undefined,
  translate: Translate,
): string | null {
  if (!reasons) return null;
  const segments = [
    reasons.genres.length ? translate("recommendations.reasonGenres", { genres: reasons.genres.join(", ") }) : "",
    reasons.franchise ? translate("recommendations.reasonFranchise") : "",
  ].filter(Boolean);
  return segments.length ? segments.join(" · ") : null;
}
