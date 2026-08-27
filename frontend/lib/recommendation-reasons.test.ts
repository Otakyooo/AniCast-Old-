import assert from "node:assert/strict";
import { test } from "node:test";
import { recommendationReasonText, type RecommendationReasons } from "./recommendation-reasons.ts";

const t = (key: string, values: Record<string, string | number> = {}) => {
  const templates: Record<string, string> = {
    "recommendations.reasonGenres": "Based on your genres: {genres}",
    "recommendations.reasonFranchise": "From your franchise",
  };
  return Object.entries(values).reduce(
    (message, [name, value]) => message.replaceAll(`{${name}}`, String(value)),
    templates[key] ?? key,
  );
};

test("reason text joins genre and franchise segments", () => {
  const reasons: RecommendationReasons = { genres: ["Драма", "Комедия"], franchise: true };
  assert.equal(
    recommendationReasonText(reasons, t),
    "Based on your genres: Драма, Комедия · From your franchise",
  );
});

test("reason text renders the single available segment", () => {
  assert.equal(recommendationReasonText({ genres: ["Драма"], franchise: false }, t), "Based on your genres: Драма");
  assert.equal(recommendationReasonText({ genres: [], franchise: true }, t), "From your franchise");
});

test("reason text stays null without reasons or matching signals", () => {
  assert.equal(recommendationReasonText(undefined, t), null);
  assert.equal(recommendationReasonText({ genres: [], franchise: false }, t), null);
});
