"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PlaybackLink } from "./playback-link";
import { ProviderPlayer } from "./provider-player";
import type { Source, WatchSourceGroup } from "../lib/api";
import { titleWatchHref } from "../lib/seo";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

interface WatchEpisode {
  number: number;
  name: string;
  synopsis?: string | null;
  air_date?: string | null;
  sources: Source[];
}

const EPISODES_PER_RANGE = 100;

function cleanSourceName(name: string, providerName = "") {
  const prefix = providerName ? `${providerName} · ` : "";
  return prefix && name.startsWith(prefix) ? name.slice(prefix.length) : name;
}

export function WatchSpace({
  slug,
  titleName,
  episodesCount,
  episodeNumbers,
  sourceGroups,
  requestedSourceKey,
  currentNumber,
  episode,
  embedded = false,
  trackProgress = false,
}: {
  slug: string;
  titleName: string;
  episodesCount: number;
  episodeNumbers: number[];
  sourceGroups: WatchSourceGroup[];
  requestedSourceKey?: string;
  currentNumber: number;
  episode: WatchEpisode;
  embedded?: boolean;
  trackProgress?: boolean;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const playableSources = episode.sources.filter((source) => source.playback_available);
  const groups = useMemo(() => {
    if (sourceGroups.length) return sourceGroups;
    const fallback = new Map<string, WatchSourceGroup>();
    for (const source of playableSources) {
      if (!source.selection_key || fallback.has(source.selection_key)) continue;
      fallback.set(source.selection_key, {
        key: source.selection_key,
        name: source.name,
        kind: source.kind,
        provider_name: source.provider_name ?? "",
        episodes_count: episodesCount,
        episode_numbers: episodeNumbers,
        popularity_percent: 0,
      });
    }
    return [...fallback.values()];
  }, [episodeNumbers, episodesCount, playableSources, sourceGroups]);
  const preferredKey = groups.some((group) => group.key === requestedSourceKey)
    ? requestedSourceKey ?? ""
    : playableSources[0]?.selection_key ?? groups[0]?.key ?? "";
  const [selectedGroupKey, setSelectedGroupKey] = useState(preferredKey);
  const [railView, setRailView] = useState<"voices" | "episodes">("episodes");

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
  const episodeRanges = useMemo(() => {
    const ranges: number[][] = [];
    for (let index = 0; index < episodeNumbers.length; index += EPISODES_PER_RANGE) {
      ranges.push(episodeNumbers.slice(index, index + EPISODES_PER_RANGE));
    }
    return ranges;
  }, [episodeNumbers]);
  const currentRangeIndex = Math.max(
    0,
    episodeRanges.findIndex((range) => range.includes(currentNumber)),
  );
  const [rangeIndex, setRangeIndex] = useState(currentRangeIndex);

  useEffect(() => setRangeIndex(currentRangeIndex), [currentRangeIndex]);

  const visibleEpisodes = episodeRanges[rangeIndex] ?? episodeNumbers;
  const currentIsAvailable = availableNumbers.has(currentNumber);

  const kindLabel = (kind: string) => t(`watch.kind.${kind}`);
  const selectedName = selectedGroup
    ? cleanSourceName(selectedGroup.name, selectedGroup.provider_name)
    : "";

  function chooseGroup(key: string) {
    setSelectedGroupKey(key);
    router.replace(titleWatchHref(slug, currentNumber, key), { scroll: false });
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
      {!embedded && (
        <header className={styles.watchHead}>
          <p className="eyebrow">{t("watch.title")} · {t("episode.number", { number: episode.number })}</p>
          <h1>{titleName}</h1>
          {episode.name && <p>{episode.name}</p>}
        </header>
      )}

      <div className={styles.watchStage}>
        <div className={styles.watchPlayer}>{player}</div>
        <aside className={styles.voiceRail} aria-label={t("watch.navigation")}>
          <div className={styles.railTabs} aria-label={t("watch.navigation")}>
            <button
              className={railView === "voices" ? styles.railTabActive : undefined}
              type="button"
              aria-pressed={railView === "voices"}
              onClick={() => setRailView("voices")}
            >
              <span>{t("watch.voicesTab")}</span>
              <b>{groups.length}</b>
            </button>
            <button
              className={railView === "episodes" ? styles.railTabActive : undefined}
              type="button"
              aria-pressed={railView === "episodes"}
              onClick={() => setRailView("episodes")}
            >
              <span>{t("title.episodes")}</span>
              <b>{episodeNumbers.length}</b>
            </button>
          </div>

          {railView === "voices" ? (
            <div className={styles.voiceList}>
              {groups.map((group) => (
                <button
                  className={`${styles.voiceButton} ${group.key === selectedGroupKey ? styles.voiceButtonActive : ""}`}
                  key={group.key}
                  type="button"
                  onClick={() => chooseGroup(group.key)}
                >
                  <span className={styles.voiceButtonTop}>
                    <strong>{cleanSourceName(group.name, group.provider_name)}</strong>
                    <b>{group.popularity_percent}%</b>
                  </span>
                  <span>{kindLabel(group.kind)} · {t("watch.choiceShare")}</span>
                </button>
              ))}
              {!groups.length && <p className="muted">{t("watch.noVoice")}</p>}
            </div>
          ) : (
            <div className={styles.episodeRail}>
              {episodeRanges.length > 1 && (
                <label className={styles.episodeRangeField}>
                  <span>{t("watch.episodeRange")}</span>
                  <select value={rangeIndex} onChange={(event) => setRangeIndex(Number(event.target.value))}>
                    {episodeRanges.map((range, index) => (
                      <option key={range[0]} value={index}>{range[0]}–{range[range.length - 1]}</option>
                    ))}
                  </select>
                </label>
              )}

              <nav className={styles.episodeGrid} aria-label={t("title.episodes")}>
                {visibleEpisodes.map((number) => {
                  const available = availableNumbers.has(number);
                  const active = number === currentNumber;
                  const className = [
                    styles.episodeButton,
                    active ? styles.episodeButtonActive : "",
                    !available ? styles.episodeButtonUnavailable : "",
                  ].filter(Boolean).join(" ");
                  return available ? (
                    <Link
                      key={number}
                      className={className}
                      href={titleWatchHref(slug, number, selectedGroupKey)}
                      aria-current={active ? "page" : undefined}
                      aria-label={t("episode.number", { number })}
                    >
                      {number}
                    </Link>
                  ) : (
                    <span
                      key={number}
                      className={className}
                      aria-disabled="true"
                      title={t("watch.episodeUnavailable")}
                    >
                      {number}
                    </span>
                  );
                })}
              </nav>
            </div>
          )}

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
