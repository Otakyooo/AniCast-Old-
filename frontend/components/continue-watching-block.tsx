"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getContinueWatching, type ContinueWatchingEntry } from "../lib/continue-watching";
import { useI18n } from "./i18n-provider";
import styles from "../app/home.module.css";

type State =
  | { kind: "loading" }
  | { kind: "guest" }
  | { kind: "error" }
  | { kind: "ready"; entries: ContinueWatchingEntry[] };

function useContinueWatching(): State {
  const [state, setState] = useState<State>({ kind: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    getContinueWatching(controller.signal)
      .then((entries) => setState(entries === null ? { kind: "guest" } : { kind: "ready", entries }))
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setState({ kind: "error" });
      });
    return () => controller.abort();
  }, []);
  return state;
}

/**
 * Home opening block per the design spec: a photo-first resume hero for the
 * freshest unfinished title, then up to five 16:9 resume cards. Guests and
 * viewers without progress see the static welcome hero instead; the real
 * catalog size grounds it with a fact instead of decoration.
 */
export function ContinueWatchingBlock({ catalogCount }: { catalogCount?: number }) {
  const { t } = useI18n();
  const state = useContinueWatching();

  if (state.kind !== "ready" || state.entries.length === 0) {
    return (
      <div className="hero">
        <p className="eyebrow">{t("home.eyebrow")}</p>
        <h1>{t("home.title")}</h1>
        <p className="muted">{t("home.subtitle")}</p>
        {typeof catalogCount === "number" && catalogCount > 0 && (
          <p className={styles.heroCount}>{t("home.catalogCount", { count: catalogCount })}</p>
        )}
        <Link className="primary inline-button" href="/catalog">{t("home.openCatalog")}</Link>
      </div>
    );
  }

  const [heroEntry, ...rest] = state.entries;
  const shelfEntries = rest.slice(0, 5);
  const heroTarget = heroEntry.next_episode ?? heroEntry.last_episode;
  const total = heroEntry.title.episodes_count;

  return (
    <>
      <section className={styles.resumeHero} aria-label={t("home.continueWatching")}>
        {heroEntry.title.poster_url && (
          <Image
            className={styles.resumeHeroArt}
            src={heroEntry.title.poster_url}
            alt=""
            fill
            priority
            sizes="100vw"
            referrerPolicy="no-referrer"
          />
        )}
        <div className={styles.resumeHeroOverlay} />
        <div className={styles.resumeHeroBody}>
          <p className={styles.resumeHeroEyebrow}>{t("home.heroEyebrow")}</p>
          <h1 className={styles.resumeHeroTitle}>{heroEntry.title.name}</h1>
          <p className={styles.resumeHeroMeta}>
            {t("episode.number", { number: heroTarget.number })}
            {total ? ` · ${t("home.heroProgress", { watched: heroEntry.watched_count, total })}` : ""}
          </p>
          <div className={styles.resumeHeroActions}>
            <Link className={`primary inline-button ${styles.resumeHeroCta}`} href={`/titles/${heroEntry.title.slug}/watch?episode=${heroTarget.number}`}>
              {t("home.continueEpisode", { number: heroTarget.number })}
            </Link>
            <Link className={`secondary inline-button ${styles.resumeHeroSecondary}`} href={`/titles/${heroEntry.title.slug}`}>
              {t("home.aboutTitle")}
            </Link>
          </div>
        </div>
      </section>

      <section className="section" aria-label={t("home.continueWatching")}>
        <div className="section-heading">
          <div className={styles.shelfHeading}>
            <h2>{t("home.continueWatching")}</h2>
          </div>
          <Link href="/history">{t("history.all")}</Link>
        </div>
        <ResumeRow entries={shelfEntries} />
      </section>
    </>
  );
}

export function ResumeRow({ entries }: { entries: ContinueWatchingEntry[] }) {
  const { t } = useI18n();
  if (entries.length === 0) return null;  return (
    <ul className={styles.resumeRow}>
      {entries.map((entry) => {
        const target = entry.next_episode ?? entry.last_episode;
        return (
          <li key={entry.title.slug}>
            <Link className={styles.resumeCard} href={`/titles/${entry.title.slug}/watch?episode=${target.number}`}>
              <span className={styles.resumeFrame}>
                {entry.title.poster_url ? (
                  <Image
                    className={styles.resumeFrameArt}
                    src={entry.title.poster_url}
                    alt=""
                    fill
                    sizes="(max-width: 767px) 45vw, 260px"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <span className={styles.resumeFallback}>{entry.title.name.charAt(0)}</span>
                )}
              </span>
              <span className={styles.resumeBody}>
                <strong>{entry.title.name}</strong>
                <small>
                  {t("episode.number", { number: target.number })}
                  {entry.title.episodes_count ? ` · ${entry.watched_count} / ${entry.title.episodes_count}` : ""}
                </small>
                <span className={styles.resumeProgressTrack}>
                  <span
                    className={styles.resumeProgressBar}
                    style={{
                      width: entry.title.episodes_count
                        ? `${Math.min(100, Math.round((entry.watched_count / entry.title.episodes_count) * 100))}%`
                        : "0%",
                    }}
                  />
                </span>
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/** Account-hub variant: just the resume row, silent when there is nothing. */
export function ResumeShelf() {
  const { t } = useI18n();
  const state = useContinueWatching();
  if (state.kind !== "ready" || state.entries.length === 0) return null;
  return (
    <section className="section" aria-label={t("home.continueWatching")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.continueWatching")}</h2>
        </div>
        <Link href="/history">{t("history.all")}</Link>
      </div>
      <ResumeRow entries={state.entries.slice(0, 5)} />
    </section>
  );
}
