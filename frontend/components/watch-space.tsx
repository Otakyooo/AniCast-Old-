"use client";

import Link from "next/link";
import { useState } from "react";
import { EpisodeProgressControl } from "./episode-progress-control";
import { PlaybackLink } from "./playback-link";
import { SourceReportControl } from "./source-report-control";
import type { Source } from "../lib/api";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

interface WatchEpisode {
  number: number;
  name: string;
  synopsis?: string | null;
  air_date?: string | null;
  sources: Source[];
}

/**
 * Unified viewing space for one title: episode rail, prev/next navigation,
 * progress control and source actions on a single shareable route
 * (/titles/<slug>/watch?episode=N). Playback stays an external provider tab —
 * the backend only issues same-origin external links by design.
 */
export function WatchSpace({
  slug,
  titleName,
  episodesCount,
  currentNumber,
  episode,
}: {
  slug: string;
  titleName: string;
  episodesCount: number;
  currentNumber: number;
  episode: WatchEpisode;
}) {
  const { t } = useI18n();
  // Rail numbers are sequential (1..count) in this catalog; a window around
  // the current episode keeps long shows manageable while 1 and the last
  // episode stay reachable.
  const windowSize = 6;
  let railStart = Math.max(1, currentNumber - windowSize);
  const railEnd = Math.min(episodesCount, currentNumber + windowSize);
  railStart = Math.max(1, railEnd - windowSize * 2);
  const railNumbers = new Set<number>([railStart, railEnd, 1, episodesCount, currentNumber]);
  for (let value = railStart; value <= railEnd; value += 1) railNumbers.add(value);
  const rail = [...railNumbers].sort((a, b) => a - b);

  const playableSources = episode.sources.filter((source) => source.playback_available);
  const [chosenSourceId, setChosenSourceId] = useState<number | null>(
    playableSources[0]?.id ?? null,
  );
  const chosen = playableSources.find((source) => source.id === chosenSourceId) ?? null;

  const sourceLabel = (value: string) =>
    t(`source.${value === "geo_blocked" ? "geo" : value === "provider_error" ? "error" : value}`);

  return (
    <div className={styles.watchLayout}>
      <header className={styles.watchHead}>
        <p className="eyebrow">{t("watch.title")} · {t("episode.number", { number: episode.number })}</p>
        <h1>{episode.name || titleName}</h1>
        {episode.synopsis && <p className="muted">{episode.synopsis}</p>}
      </header>

      <nav className={styles.watchNav} aria-label={t("title.episodes")}>
        {currentNumber > 1 ? (
          <Link className={styles.railLink} href={`/titles/${slug}/watch?episode=${currentNumber - 1}`}>
            ← {t("watch.prev")}
          </Link>
        ) : <span />}
        {currentNumber < episodesCount ? (
          <Link className={styles.railLink} href={`/titles/${slug}/watch?episode=${currentNumber + 1}`}>
            {t("watch.next")} →
          </Link>
        ) : <span />}
      </nav>

      <nav className={styles.rail} aria-label={t("episode.number", { number: currentNumber })}>
        {rail.map((value, index) => (
          <span key={value} className={styles.railGap}>
            {index > 0 && value - rail[index - 1] > 1 && <span className={styles.railEllipsis}>…</span>}
            <Link
              className={`${styles.railLink} ${value === currentNumber ? styles.railActive : ""}`}
              href={`/titles/${slug}/watch?episode=${value}`}
              aria-current={value === currentNumber ? "page" : undefined}
            >
              {value}
            </Link>
          </span>
        ))}
      </nav>

      <EpisodeProgressControl slug={slug} number={episode.number} />

      <section className={styles.watchSources}>
        <h2>{t("episode.sources")}</h2>
        <p className="muted">{t("watch.sourcesHint")}</p>
        {playableSources.length ? (
          <>
            <div className={styles.sourceRow}>
              {chosen ? (
                <PlaybackLink key={chosen.id} sourceId={chosen.id} />
              ) : null}
              {playableSources.length > 1 && (
                <select
                  aria-label={t("episode.sources")}
                  value={chosenSourceId ?? ""}
                  onChange={(event) => setChosenSourceId(Number(event.target.value))}
                >
                  {playableSources.map((source) => (
                    <option key={source.id} value={source.id}>
                      {source.name} · {source.kind.toUpperCase()}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <ul className="source-list">
              {episode.sources.map((source) => (
                <li className={`source-status source-status-${source.availability}`} key={`${source.name}-${source.kind}`}>
                  <span className="source-status-main">
                    <strong>{source.name}</strong>
                    <span>{source.kind.toUpperCase()}</span>
                  </span>
                  <span className="source-status-label">{sourceLabel(source.availability)}</span>
                  <SourceReportControl sourceId={source.id} />
                </li>
              ))}
            </ul>
          </>
        ) : (
          <div className="empty-state"><strong>{t("episode.noSources")}</strong></div>
        )}
      </section>
    </div>
  );
}
