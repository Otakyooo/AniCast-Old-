export interface EpisodeCoverageSummary {
  count: number;
  first: number | null;
  last: number | null;
  density: number;
  availableRanges: string[];
  missingRanges: string[];
}

function normalizedEpisodeNumbers(numbers: number[]) {
  return [...new Set(numbers)]
    .filter((number) => Number.isInteger(number) && number > 0)
    .sort((left, right) => left - right);
}

function rangeLabel(first: number, last: number) {
  return first === last ? String(first) : `${first}–${last}`;
}

/** Exact available and missing ranges derived from real episode numbers. */
export function summarizeEpisodeCoverage(numbers: number[]): EpisodeCoverageSummary {
  const normalized = normalizedEpisodeNumbers(numbers);
  if (!normalized.length) {
    return {
      count: 0,
      first: null,
      last: null,
      density: 0,
      availableRanges: [],
      missingRanges: [],
    };
  }

  const availableRanges: string[] = [];
  const missingRanges: string[] = [];
  let start = normalized[0];
  let end = start;

  for (const number of normalized.slice(1)) {
    if (number === end + 1) {
      end = number;
      continue;
    }
    availableRanges.push(rangeLabel(start, end));
    missingRanges.push(rangeLabel(end + 1, number - 1));
    start = number;
    end = number;
  }
  availableRanges.push(rangeLabel(start, end));

  return {
    count: normalized.length,
    first: normalized[0],
    last: normalized.at(-1) ?? normalized[0],
    density: normalized.length / (end - normalized[0] + 1),
    availableRanges,
    missingRanges,
  };
}
