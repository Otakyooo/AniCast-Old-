import type { CatalogItem } from "./api";
import { getCsrfToken } from "./auth";
import type { RecommendationReasons } from "./recommendation-reasons";

export interface Recommendation {
  title: CatalogItem;
  score: number;
  reasons?: RecommendationReasons;
}

export interface RecommendationResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Recommendation[];
}

export async function getRecommendations(page = 1, signal?: AbortSignal) {
  const response = await fetch(`/api/v1/recommendations/?page=${page}`, { credentials: "same-origin", cache: "no-store", signal });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new Error("Recommendations request failed");
  return response.json() as Promise<RecommendationResponse>;
}

async function mutateDismissal(slug: string, method: "POST" | "DELETE"): Promise<boolean | null> {
  const csrf = await getCsrfToken();
  const response = await fetch(`/api/v1/recommendations/${encodeURIComponent(slug)}/dismiss/`, {
    method,
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrf },
  });
  if (response.status === 401 || response.status === 403) return null;
  return response.ok;
}

/** Hides a title from personal recommendations. Null means the session ended. */
export function dismissRecommendation(slug: string) {
  return mutateDismissal(slug, "POST");
}

/** Restores a dismissed title; false when the dismissal no longer exists. */
export function undismissRecommendation(slug: string) {
  return mutateDismissal(slug, "DELETE");
}
