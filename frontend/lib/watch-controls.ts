export type VoiceSection = "dub" | "sub" | "raw";

/** Keep the provider order while removing invalid and duplicate episode numbers. */
export function normalizeEpisodeNumbers(numbers: number[]) {
  const unique = new Set(
    numbers.filter((number) => Number.isInteger(number) && number > 0),
  );
  return [...unique].sort((left, right) => left - right);
}

/** Episode search is deliberately numeric: viewers use it as a quick jump. */
export function filterEpisodeNumbers(numbers: number[], query: string) {
  const normalized = normalizeEpisodeNumbers(numbers);
  if (!query.trim()) return normalized;
  const digits = query.replace(/\D/g, "");
  if (!digits) return [];

  const exact = Number(digits);
  const matches = normalized.filter((number) => String(number).startsWith(digits));
  if (!matches.includes(exact)) return matches;
  return [exact, ...matches.filter((number) => number !== exact)];
}

export function voiceSection(kind: string): VoiceSection {
  if (kind === "sub") return "sub";
  if (kind === "raw") return "raw";
  return "dub";
}

export function resolveRequestedGroupKey<
  T extends { key: string; legacy_key?: string | null },
>(groups: T[], requestedKey?: string) {
  if (!requestedKey) return null;
  const exact = groups.find((group) => group.key === requestedKey);
  if (exact) return { key: exact.key, legacy: false };
  const legacy = groups.find((group) => group.legacy_key === requestedKey);
  return legacy ? { key: legacy.key, legacy: true } : null;
}
