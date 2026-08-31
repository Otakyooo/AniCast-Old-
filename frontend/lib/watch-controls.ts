import type { Source, WatchSourceGroup } from "./api.ts";

export type VoiceSection = "dub" | "sub" | "raw";

export type ResolvedWatchSourceGroup = WatchSourceGroup & { coverage_known: boolean };

export interface EpisodeNumberRange {
  first: number;
  last: number;
  numbers: number[];
}

/** Keep the provider order while removing invalid and duplicate episode numbers. */
export function normalizeEpisodeNumbers(numbers: number[]) {
  const unique = new Set(
    numbers.filter((number) => Number.isInteger(number) && number > 0),
  );
  return [...unique].sort((left, right) => left - right);
}

/**
 * Reconcile the short-lived episode detail with the cached navigation matrix.
 * The current episode is authoritative, while cached coverage keeps its order.
 */
export function mergeCurrentWatchSourceGroups(
  sourceGroups: WatchSourceGroup[],
  currentSources: Source[],
  currentNumber: number,
  singlePlayback = false,
): ResolvedWatchSourceGroup[] {
  const currentKeys = new Set(
    currentSources.map((source) => source.selection_key).filter(Boolean),
  );
  const merged = new Map<string, ResolvedWatchSourceGroup>();
  for (const group of sourceGroups) {
    const episodeNumbers = normalizeEpisodeNumbers(group.episode_numbers)
      .filter((number) => number !== currentNumber || currentKeys.has(group.key));
    merged.set(group.key, {
      ...group,
      episodes_count: episodeNumbers.length,
      episode_numbers: episodeNumbers,
      coverage_known: true,
    });
  }

  for (const source of currentSources) {
    if (!source.selection_key) continue;
    const existing = merged.get(source.selection_key);
    if (existing) {
      const episodeNumbers = normalizeEpisodeNumbers([
        ...existing.episode_numbers,
        currentNumber,
      ]);
      merged.set(source.selection_key, {
        ...existing,
        name: source.name,
        kind: source.kind,
        provider_name: source.provider_name ?? existing.provider_name,
        provider_variant_id: source.provider_variant_id ?? existing.provider_variant_id,
        episodes_count: episodeNumbers.length,
        episode_numbers: episodeNumbers,
      });
      continue;
    }
    merged.set(source.selection_key, {
      key: source.selection_key,
      name: source.name,
      kind: source.kind,
      provider_name: source.provider_name ?? "",
      provider_variant_id: source.provider_variant_id,
      episodes_count: 1,
      episode_numbers: [currentNumber],
      popularity_percent: 0,
      coverage_known: false,
    });
  }

  const options = [...merged.values()].filter((group) => group.episode_numbers.length > 0);
  return singlePlayback
    ? options.filter((group) => currentKeys.has(group.key))
    : options;
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

/** Keep long-running series usable without rendering a thousand links at once. */
export function episodeNumberRanges(numbers: number[], size = 100): EpisodeNumberRange[] {
  const normalized = normalizeEpisodeNumbers(numbers);
  const pageSize = Number.isInteger(size) && size > 0 ? size : 100;
  const ranges: EpisodeNumberRange[] = [];
  for (let index = 0; index < normalized.length; index += pageSize) {
    const slice = normalized.slice(index, index + pageSize);
    ranges.push({
      first: slice[0],
      last: slice.at(-1) ?? slice[0],
      numbers: slice,
    });
  }
  return ranges;
}

export function episodeRangeIndex(ranges: EpisodeNumberRange[], currentNumber: number) {
  const exact = ranges.findIndex((range) => range.numbers.includes(currentNumber));
  if (exact >= 0) return exact;
  const next = ranges.findIndex((range) => range.last >= currentNumber);
  return next >= 0 ? next : Math.max(0, ranges.length - 1);
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

/** Pick the first API-ranked option that has a playable source for this episode. */
export function firstRankedPlayableGroupKey<
  T extends { key: string; episode_numbers?: number[] },
>(groups: T[], playableKeys: string[], currentNumber: number) {
  const playable = new Set(playableKeys);
  const ranked = groups.find((group) => (
    playable.has(group.key)
    && (!group.episode_numbers || group.episode_numbers.includes(currentNumber))
  ));
  return ranked?.key ?? playableKeys[0] ?? groups[0]?.key ?? "";
}
