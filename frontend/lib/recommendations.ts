import type { CatalogItem } from "./api";

export interface Recommendation { title: CatalogItem; score: number }
export interface RecommendationResponse { count: number; next: string | null; previous: string | null; results: Recommendation[] }

export async function getRecommendations(signal?: AbortSignal) {
  const response = await fetch("/api/v1/recommendations/", { credentials: "same-origin", cache: "no-store", signal });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new Error("Recommendations request failed");
  return response.json() as Promise<RecommendationResponse>;
}
