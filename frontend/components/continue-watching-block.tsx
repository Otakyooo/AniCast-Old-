"use client";

import Image from "next/image";
import Link from "next/link";
import { Check, Play, Plus } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import type { CatalogItem } from "../lib/api";
import { getContinueWatching, resumeEpisode, type ContinueWatchingEntry } from "../lib/continue-watching";
import { getLibraryEntry, LibraryApiError, putLibraryEntry, type LibraryEntry, type LibraryStatus } from "../lib/library";
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

function HeroLibraryAction({ slug, initialStatus }: { slug: string; initialStatus: LibraryStatus }) {
  const { t } = useI18n();
  const [entry, setEntry] = useState<LibraryEntry | null | undefined>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setEntry(undefined);
    setGuest(false);
    setError("");

    getLibraryEntry(slug, controller.signal)
      .then(setEntry)
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        if (reason instanceof LibraryApiError && [401, 403].includes(reason.status)) setGuest(true);
        else setError(t("common.error"));
      });

    return () => controller.abort();
  }, [retryKey, slug, t]);

  async function addToLibrary() {
    setPending(true);
    setError("");
    try {
      setEntry(await putLibraryEntry(slug, { status: initialStatus, is_favorite: false }));
    } catch (reason) {
      if (reason instanceof LibraryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(t("common.error"));
    } finally {
      setPending(false);
    }
  }

  if (guest) {
    return <Link className={`secondary inline-button ${styles.resumeHeroSecondary}`} href="/login"><Plus aria-hidden="true" size={20} />{t("home.signInToSave")}</Link>;
  }

  if (entry) {
    return <Link className={`secondary inline-button ${styles.resumeHeroSecondary}`} href="/library"><Check aria-hidden="true" weight="bold" size={20} />{t("title.inLibrary")}</Link>;
  }

  if (entry === undefined && error) {
    return (
      <span className={styles.heroLibraryState}>
        <button className={`secondary inline-button ${styles.resumeHeroSecondary}`} type="button" onClick={() => setRetryKey((value) => value + 1)}>{t("common.retry")}</button>
        <span className={styles.heroActionError} role="alert">{error}</span>
      </span>
    );
  }

  return (
    <span className={styles.heroLibraryState}>
      <button
        className={`secondary inline-button ${styles.resumeHeroSecondary}`}
        type="button"
        disabled={pending || entry === undefined}
        onClick={addToLibrary}
      >
        <Plus aria-hidden="true" size={20} />
        {pending ? t("home.addingLibrary") : entry === undefined ? t("common.loading") : t("title.addLibrary")}
      </button>
      {error && <span className={styles.heroActionError} role="alert">{error}</span>}
    </span>
  );
}

/**
 * Home opening block per the design spec: a photo-first resume hero for the
 * freshest unfinished title, then up to five 16:9 resume cards. Guests and
 * viewers without progress see the static welcome hero instead; the real
 * catalog size grounds it with a fact instead of decoration.
 */
export function ContinueWatchingBlock({ catalogCount, featured }: { catalogCount?: number; featured?: CatalogItem }) {
  const { t } = useI18n();
  const state = useContinueWatching();
  const entries = state.kind === "ready" ? state.entries : [];
  const [heroEntry, ...rest] = entries;
  const shelfEntries = rest.slice(0, 7);
  const displayTitle = heroEntry?.title ?? featured;
  const heroTarget = heroEntry ? resumeEpisode(heroEntry) ?? undefined : undefined;
  const total = displayTitle?.episodes_count;
  const primaryHref = heroEntry && heroTarget
    ? `/titles/${heroEntry.title.slug}?episode=${heroTarget.number}`
    : displayTitle?.episodes_count
      ? `/titles/${displayTitle.slug}?episode=1`
      : displayTitle ? `/titles/${displayTitle.slug}` : "/catalog";
  const metadata = displayTitle
    ? [displayTitle.year, displayTitle.title_type ? t(`type.${displayTitle.title_type}`) : null, total ? t("home.episodeCount", { count: total }) : null].filter(Boolean)
    : [];

  return (
    <>
      <section className={styles.resumeHero} aria-label={t("home.continueWatching")}>
        {displayTitle?.poster_url ? (
          <>
            <div className={styles.resumeHeroBackdrop} aria-hidden="true">
              <Image
                className={styles.resumeHeroBackdropArt}
                src={displayTitle.poster_url}
                alt=""
                fill
                sizes="(max-width: 520px) 100vw, (max-width: 1199px) 72vw, 66vw"
                quality={92}
                referrerPolicy="no-referrer"
              />
            </div>
            <div className={styles.resumeHeroArtFrame} aria-hidden="true">
              <Image
                className={styles.resumeHeroArt}
                src={displayTitle.poster_url}
                alt=""
                fill
                priority
                sizes="(max-width: 520px) 92px, 164px"
                quality={92}
                referrerPolicy="no-referrer"
              />
            </div>
          </>
        ) : null}
        <div className={styles.resumeHeroBody}>
          <p className={styles.resumeHeroEyebrow}>{heroEntry ? t("home.heroEyebrow") : t("home.featuredEyebrow")}</p>
          <h1 className={styles.resumeHeroTitle}>{displayTitle?.name ?? t("home.title")}</h1>
          {metadata.length > 0 && <p className={styles.resumeHeroMeta}>{metadata.join(" · ")}</p>}
          {displayTitle?.genres?.length ? (
            <ul className={styles.heroGenres} aria-label={t("catalog.genre")}>
              {displayTitle.genres.slice(0, 3).map((genre) => <li key={genre.slug}>{genre.name}</li>)}
            </ul>
          ) : null}
          {displayTitle?.synopsis && <p className={styles.heroSynopsis}>{displayTitle.synopsis}</p>}
          <div className={styles.resumeHeroActions}>
            <Link className={`primary inline-button ${styles.resumeHeroCta}`} href={primaryHref}>
              <Play aria-hidden="true" weight="fill" size={19} />
              {heroEntry && heroTarget ? t("home.continueEpisode", { number: heroTarget.number }) : t("home.watchFeatured")}
            </Link>
            {displayTitle && <HeroLibraryAction slug={displayTitle.slug} initialStatus={heroEntry ? "watching" : "planned"} />}
          </div>
          {heroEntry && heroTarget && total ? (
            <div className={styles.heroProgress}>
              <span><i style={{ width: `${Math.min(100, Math.round((heroEntry.watched_count / total) * 100))}%` }} /></span>
              <small>{t("home.heroProgress", { watched: heroEntry.watched_count, total })}</small>
            </div>
          ) : !heroEntry && typeof catalogCount === "number" && catalogCount > 0 ? (
            <small className={styles.catalogFact}>{t("home.catalogCount", { count: catalogCount })}</small>
          ) : null}
        </div>
      </section>

      {shelfEntries.length > 0 && <section className="section" aria-label={t("home.continueWatching")}>
        <div className="section-heading">
          <div className={styles.shelfHeading}>
            <h2>{t("home.continueWatching")}</h2>
          </div>
          <Link href="/history">{t("history.all")}</Link>
        </div>
        <ResumeRow entries={shelfEntries} />
      </section>}
    </>
  );
}

export function ResumeRow({ entries }: { entries: ContinueWatchingEntry[] }) {
  const { t } = useI18n();
  if (entries.length === 0) return null;  return (
    <ul className={styles.resumeRow}>
      {entries.map((entry) => {
        const target = resumeEpisode(entry);
        if (!target) return null;
        return (
          <li key={entry.title.slug}>
            <Link className={styles.resumeCard} href={`/titles/${entry.title.slug}?episode=${target.number}`}>
              <span className={styles.resumeFrame}>
                {entry.title.poster_url ? (
                  <Image
                    className={styles.resumeFrameArt}
                    src={entry.title.poster_url}
                    alt=""
                    fill
                    sizes="(max-width: 767px) 45vw, 260px"
                    quality={92}
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
