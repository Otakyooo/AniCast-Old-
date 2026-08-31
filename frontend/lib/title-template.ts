export type PlaybackPresentation = "episodic" | "single";

export interface TitleTemplateState {
  playbackPresentation: PlaybackPresentation;
  showEpisodeCount: boolean;
  showEpisodeTab: boolean;
  structuredEpisodeCount: number | null;
}

export interface ResolvedTitleEpisodeRequest {
  number: number;
  corrected: boolean;
}

function normalizedEpisodeCount(value: number | undefined) {
  return Number.isInteger(value) && (value ?? 0) > 0 ? value as number : 0;
}

/**
 * Shared presentation rules for every title page.
 *
 * Movies are a single playback unit even when imported metadata contains
 * provider-less "Part N" rows. OVA/special titles use the same compact
 * presentation only while they genuinely contain at most one episode.
 */
export function titleTemplateState(
  titleType: string | null | undefined,
  episodesCount: number | undefined,
): TitleTemplateState {
  const count = normalizedEpisodeCount(episodesCount);
  const single = titleType === "movie"
    || ((titleType === "ova" || titleType === "special") && count <= 1);
  const hasEpisodeCollection = count > 0 && !single;

  return {
    playbackPresentation: single ? "single" : "episodic",
    showEpisodeCount: hasEpisodeCollection,
    showEpisodeTab: hasEpisodeCollection,
    structuredEpisodeCount: hasEpisodeCollection ? count : null,
  };
}

/** Resolve query state without inventing episodes or changing title layout. */
export function resolveTitleEpisodeRequest(
  presentation: PlaybackPresentation,
  fallbackNumber: number,
  requestedValue: string | undefined,
  catalogEpisodeNumbers?: number[],
): ResolvedTitleEpisodeRequest {
  if (requestedValue === undefined) {
    return { number: fallbackNumber, corrected: false };
  }

  const requestedNumber = Number(requestedValue);
  const valid = Number.isInteger(requestedNumber) && requestedNumber > 0;
  const known = catalogEpisodeNumbers !== undefined;
  const exists = !known || catalogEpisodeNumbers.includes(requestedNumber);
  if (presentation === "single" || !valid || !exists) {
    return {
      number: fallbackNumber,
      corrected: !valid || requestedNumber !== fallbackNumber,
    };
  }
  return { number: requestedNumber, corrected: false };
}
