"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "react";
import { PlaybackLink } from "./playback-link";
import { ProviderPlayer } from "./provider-player";
import type { Source, WatchSourceGroup } from "../lib/api";
import { summarizeEpisodeCoverage } from "../lib/episode-coverage";
import { titleWatchHref } from "../lib/seo";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

interface WatchEpisode {
  synopsis?: string | null;
  sources: Source[];
}

type Translator = (key: string, values?: Record<string, string | number>) => string;
type ViewSourceGroup = WatchSourceGroup & { coverage_known: boolean };

function cleanSourceName(name: string, providerName = "") {
  const prefix = providerName ? `${providerName} · ` : "";
  return prefix && name.startsWith(prefix) ? name.slice(prefix.length) : name;
}

function coverageLabels(numbers: number[], t: Translator, known = true) {
  if (!known) {
    const unknown = t("watch.coverageUnknown");
    return { compact: unknown, full: unknown, compactIsExact: false };
  }
  const summary = summarizeEpisodeCoverage(numbers);
  if (!summary.count || summary.first === null || summary.last === null) {
    const empty = t("watch.coverageEmpty");
    return { compact: empty, full: empty, compactIsExact: true };
  }
  if (summary.count === 1) {
    const single = t("watch.coverageSingle", { number: summary.first });
    return { compact: single, full: single, compactIsExact: true };
  }

  const full = t("watch.coverageRanges", { ranges: summary.availableRanges.join(", ") });
  const except = t("watch.coverageExcept", {
    first: summary.first,
    last: summary.last,
    missing: summary.missingRanges.join(", "),
  });
  if (
    summary.missingRanges.length > 0
    && summary.missingRanges.length <= 3
    && summary.density >= 0.8
    && except.length < full.length
  ) {
    return { compact: except, full, compactIsExact: true };
  }
  if (summary.availableRanges.length <= 3) {
    return { compact: full, full, compactIsExact: true };
  }
  return {
    compact: t("watch.coverageWithGaps", {
      count: summary.count,
      first: summary.first,
      last: summary.last,
    }),
    full,
    compactIsExact: false,
  };
}

export function WatchSpace({
  slug,
  episodeNumbers,
  sourceGroups,
  requestedSourceKey,
  currentNumber,
  episode,
  trackProgress = false,
}: {
  slug: string;
  episodeNumbers: number[];
  sourceGroups: WatchSourceGroup[];
  requestedSourceKey?: string;
  currentNumber: number;
  episode: WatchEpisode;
  trackProgress?: boolean;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const playableSources = episode.sources.filter((source) => source.playback_available);
  const groups = useMemo<ViewSourceGroup[]>(() => {
    if (sourceGroups.length) {
      return sourceGroups.map((group) => ({ ...group, coverage_known: true }));
    }
    const fallback = new Map<string, ViewSourceGroup>();
    for (const source of playableSources) {
      if (!source.selection_key || fallback.has(source.selection_key)) continue;
      fallback.set(source.selection_key, {
        key: source.selection_key,
        name: source.name,
        kind: source.kind,
        provider_name: source.provider_name ?? "",
        episodes_count: 1,
        episode_numbers: [currentNumber],
        popularity_percent: 0,
        coverage_known: false,
      });
    }
    return [...fallback.values()];
  }, [currentNumber, playableSources, sourceGroups]);
  const preferredKey = groups.some((group) => group.key === requestedSourceKey)
    ? requestedSourceKey ?? ""
    : playableSources[0]?.selection_key ?? groups[0]?.key ?? "";
  const [selectedGroupKey, setSelectedGroupKey] = useState(preferredKey);

  useEffect(() => {
    setSelectedGroupKey(preferredKey);
  }, [currentNumber, preferredKey]);

  const selectedGroup = groups.find((group) => group.key === selectedGroupKey) ?? null;
  const selectedSources = playableSources.filter((source) => source.selection_key === selectedGroupKey);
  const chosen = selectedSources[0] ?? null;
  const availableNumbers = useMemo(
    () => new Set(selectedGroup?.episode_numbers ?? episodeNumbers),
    [episodeNumbers, selectedGroup],
  );
  const currentIsAvailable = availableNumbers.has(currentNumber);
  const availableEpisodeNumbers = episodeNumbers.filter((number) => availableNumbers.has(number));
  const previousNumber = availableEpisodeNumbers.filter((number) => number < currentNumber).at(-1);
  const nextNumber = availableEpisodeNumbers.find((number) => number > currentNumber);
  const selectedCoverageNumbers = selectedGroup?.episode_numbers ?? [];
  const selectedCoverage = coverageLabels(
    selectedCoverageNumbers,
    t,
    selectedGroup?.coverage_known ?? true,
  );

  const kindLabel = (kind: string) => t(`watch.kind.${kind}`);
  const selectedName = selectedGroup
    ? cleanSourceName(selectedGroup.name, selectedGroup.provider_name)
    : "";

  function chooseGroup(key: string) {
    setSelectedGroupKey(key);
    router.replace(titleWatchHref(slug, currentNumber, key), { scroll: false });
  }

  function chooseEpisode(number: string) {
    router.push(titleWatchHref(slug, Number(number), selectedGroupKey), { scroll: false });
  }

  const player = chosen?.playback_mode === "iframe_embed" ? (
    <ProviderPlayer
      key={chosen.id}
      sourceId={chosen.id}
      playbackMode={chosen.playback_mode}
      title={`${selectedName} · ${t("episode.number", { number: currentNumber })}`}
      slug={slug}
      episodeNumber={currentNumber}
      trackProgress={trackProgress}
    />
  ) : chosen ? (
    <section className={`${styles.playerShell} ${styles.playerPreview}`}>
      <div className={styles.playerBar}>
        <strong>{selectedName} · {t("episode.number", { number: currentNumber })}</strong>
        <span>{kindLabel(chosen.kind)}</span>
      </div>
      <div className={styles.playerPreviewBody}>
        <PlaybackLink
          sourceId={chosen.id}
          playbackMode={chosen.playback_mode}
          slug={slug}
          episodeNumber={currentNumber}
          label={t("watch.playEpisode", { number: currentNumber })}
          className={styles.playerLaunch}
        />
      </div>
    </section>
  ) : (
    <div className={styles.watchEmpty}>
      <strong>{t("watch.noPlayer")}</strong>
      <span>{t("watch.chooseAvailableEpisode")}</span>
    </div>
  );

  return (
    <div className={styles.watchLayout}>
      <div className={styles.watchStage}>
        <div className={styles.watchPlayer}>{player}</div>
        <aside className={styles.voiceRail} aria-label={t("watch.navigation")}>
          <div className={styles.voiceSelect}>
            <label htmlFor="watch-voice-select">{t("watch.voice")}</label>
            <select
              id="watch-voice-select"
              aria-describedby={selectedGroup ? "watch-voice-coverage" : undefined}
              value={selectedGroupKey}
              disabled={!groups.length}
              onChange={(event) => chooseGroup(event.target.value)}
            >
              {groups.map((group) => (
                <option key={group.key} value={group.key}>
                  {t("watch.voiceOption", {
                    name: cleanSourceName(group.name, group.provider_name),
                    coverage: coverageLabels(group.episode_numbers, t, group.coverage_known).compact,
                  })}
                </option>
              ))}
              {!groups.length && <option value="">{t("watch.noVoice")}</option>}
            </select>
            {selectedGroup && (
              <div className={styles.voiceCoverage} id="watch-voice-coverage">
                {selectedCoverage.compactIsExact ? (
                  <span>{t("watch.voiceCoverage", { coverage: selectedCoverage.compact })}</span>
                ) : selectedCoverage.full === selectedCoverage.compact ? (
                  <span>{t("watch.voiceCoverage", { coverage: selectedCoverage.compact })}</span>
                ) : (
                  <details>
                    <summary>{t("watch.voiceCoverage", { coverage: selectedCoverage.compact })}</summary>
                    <p>{t("watch.voiceCoverage", { coverage: selectedCoverage.full })}</p>
                  </details>
                )}
              </div>
            )}
          </div>

          <div className={styles.episodePicker}>
            <span>{t("title.episodes")}</span>
            <div className={styles.episodePickerControls}>
              {previousNumber !== undefined ? (
                <Link
                  href={titleWatchHref(slug, previousNumber, selectedGroupKey)}
                  aria-label={t("watch.prev")}
                  title={t("watch.prev")}
                >
                  <CaretLeft aria-hidden="true" weight="bold" />
                </Link>
              ) : (
                <span aria-disabled="true"><CaretLeft aria-hidden="true" weight="bold" /></span>
              )}
              <label className={styles.episodeSelect}>
                <span>{t("watch.chooseEpisode")}</span>
                <select
                  value={String(currentNumber)}
                  disabled={!availableEpisodeNumbers.length}
                  onChange={(event) => chooseEpisode(event.target.value)}
                >
                  {!currentIsAvailable && (
                    <option value={currentNumber} disabled>
                      {t("watch.episodeUnavailableCurrent", { number: currentNumber })}
                    </option>
                  )}
                  {availableEpisodeNumbers.map((number) => (
                    <option key={number} value={number}>
                      {number}
                    </option>
                  ))}
                </select>
              </label>
              {nextNumber !== undefined ? (
                <Link
                  href={titleWatchHref(slug, nextNumber, selectedGroupKey)}
                  aria-label={t("watch.next")}
                  title={t("watch.next")}
                >
                  <CaretRight aria-hidden="true" weight="bold" />
                </Link>
              ) : (
                <span aria-disabled="true"><CaretRight aria-hidden="true" weight="bold" /></span>
              )}
            </div>
          </div>

          {!currentIsAvailable && selectedGroup && (
            <p className={styles.watchWarning} role="status">
              {t("watch.voiceUnavailable", { number: currentNumber, name: selectedName })}
            </p>
          )}
        </aside>
      </div>

      {episode.synopsis && <p className={styles.watchSynopsis}>{episode.synopsis}</p>}
    </div>
  );
}
