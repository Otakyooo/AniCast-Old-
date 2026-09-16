"use client";

import Image from "next/image";
import Link from "next/link";
import { DotsThree, Play } from "@phosphor-icons/react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { CatalogItem } from "../lib/api";
import {
  ContinueWatchingApiError,
  getContinueWatching,
  hideFromContinueWatching,
  resumeEpisode,
  resumeEpisodeStarted,
  resumeProgressPercent,
  unhideFromContinueWatching,
  type ContinueWatchingEntry,
} from "../lib/continue-watching";
import { formatPlaybackTime } from "../lib/playback";
import { titleWatchHref } from "../lib/seo";
import { episodeCountLabel } from "../lib/episode-count";
import type { Locale } from "../i18n/config";
import { useI18n } from "./i18n-provider";
import styles from "../app/home.module.css";

/** The shelf carries up to twelve entries: one featured card and eleven rows.
 *  Everything past that lives on /history, so a heavy viewer's home page stays
 *  short while the full list stays one click away. */
const VISIBLE_LIMIT = 12;

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

/** The playable voice variant the viewer actually used last (`dub/sub/raw`). */
function voiceLabel(entry: ContinueWatchingEntry, t: (key: string, values?: Record<string, string | number>) => string): string {
  if (!entry.source_name) return "";
  const kindLabel = entry.source_kind === "dub"
    ? t("watch.voiceGroup.dub")
    : entry.source_kind === "sub"
      ? t("watch.voiceGroup.sub")
      : t("watch.voiceGroup.raw");
  return `${kindLabel}: ${entry.source_name}`;
}

/** Single line describing the resume state ("Серия 4 · 08:32 / 24:10" etc).
 *
 *  The line follows what actually happens when the viewer presses play: an
 *  episode with a real position shows where it stopped, an episode that was
 *  never started is announced as the one to begin with. */
function resumeFactLine(
  entry: ContinueWatchingEntry,
  t: (key: string, values?: Record<string, string | number>) => string,
): string {
  const target = resumeEpisode(entry);
  if (!target) return "";
  const position = entry.resume_at_seconds ?? 0;
  if (position > 0) {
    const duration = typeof entry.duration_seconds === "number" && entry.duration_seconds > 0
      ? entry.duration_seconds
      : null;
    // "Серия 4 · 08:32 / 24:10" — the position inside the episode that
    // actually resumes, not a share of the whole series.
    const time = duration !== null
      ? `${formatPlaybackTime(position)} / ${formatPlaybackTime(duration)}`
      : formatPlaybackTime(position);
    return t("home.episodeProgressLine", { number: target.number, time });
  }
  return t("home.startEpisode", { number: target.number });
}

/** Secondary line with the count of watched episodes when it says something new. */
function resumeCountLine(
  entry: ContinueWatchingEntry,
  locale: Locale,
  t: (key: string, values?: Record<string, string | number>) => string,
): string {
  const total = entry.title.episodes_count;
  if (typeof total !== "number" || total <= 0 || entry.watched_count <= 0) return "";
  return t("home.episodesWatched", { count: episodeCountLabel(t, locale, entry.watched_count), total });
}

/** Small ⋯ menu: hide from this shelf with an undo window; never touches history. */
function ContinueMenu({
  entry,
  onRemoved,
}: {
  entry: ContinueWatchingEntry;
  onRemoved: (slug: string) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const menuId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const timerRef = useRef<number | null>(null);

  const close = useCallback(() => setOpen(false), []);

  // Eight seconds until the row leaves the shelf for good. Extracted because a
  // failed undo has to re-arm it: the row is still hidden server-side, so
  // leaving the timer cleared would keep it stuck in the undo state forever.
  const armRemoval = useCallback(() => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => onRemoved(entry.title.slug), 8000);
  }, [entry.title.slug, onRemoved]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) close();
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        close();
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, close]);

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
  }, []);

  async function hide() {
    setPending(true);
    setError("");
    try {
      await hideFromContinueWatching(entry.title.slug);
      setHidden(true);
      armRemoval();
    } catch (reason) {
      setError(reason instanceof ContinueWatchingApiError && [401, 403].includes(reason.status)
        ? t("common.login")
        : t("home.removeHistoryFailed"));
    } finally {
      setPending(false);
    }
  }

  async function undo() {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    setPending(true);
    setError("");
    try {
      await unhideFromContinueWatching(entry.title.slug);
      setHidden(false);
    } catch {
      // The hide still stands on the server; the row has to leave the shelf
      // anyway, and the viewer needs to see why nothing came back.
      setError(t("home.removeHistoryFailed"));
      armRemoval();
    } finally {
      setPending(false);
    }
  }

  if (hidden) {
    return (
      <div className={styles.continueUndo} role="status">
        <span>{t("home.continueRemoved")}</span>
        <button type="button" disabled={pending} onClick={undo}>{t("home.undo")}</button>
        {error && <span className={styles.continueMenuError} role="alert">{error}</span>}
      </div>
    );
  }

  return (
    <div className={styles.continueMenuWrap} ref={containerRef}>
      <button
        ref={triggerRef}
        className={styles.continueMenuButton}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={t("home.continueMenu")}
        onClick={() => setOpen((value) => !value)}
      >
        <DotsThree aria-hidden="true" size={18} weight="bold" />
      </button>
      {open && (
        <div className={styles.continueMenu} id={menuId} role="menu">
          <button type="button" role="menuitem" disabled={pending} onClick={() => { close(); void hide(); }}>
            {t("home.removeFromContinue")}
          </button>
        </div>
      )}
      {error && <span className={styles.continueMenuError} role="alert">{error}</span>}
    </div>
  );
}

/** One compact resume row: thumb, name, fact, voice, explicit play, ⋯ menu. */
export function ResumeCard({
  entry,
  onRemoved,
  variant = "row",
}: {
  entry: ContinueWatchingEntry;
  onRemoved?: (slug: string) => void;
  variant?: "row" | "feature";
}) {
  const { t, locale } = useI18n();
  const target = resumeEpisode(entry);
  if (!target) return null;

  const title = entry.title;
  const playHref = titleWatchHref(title.slug, target.number, entry.source_selection_key || undefined);
  // The play button must name what actually starts: an episode with a saved
  // position is continued, an episode that was never started is one to begin
  // with. `is_watched` is not the signal — a finished episode hands over to the
  // next one, which has no position of its own either.
  const started = resumeEpisodeStarted(entry);
  const playLabel = started
    ? t("home.continueEpisode", { number: target.number })
    : t("home.startEpisode", { number: target.number });
  const factLine = resumeFactLine(entry, t);
  const countLine = resumeCountLine(entry, locale, t);
  const voiceLine = voiceLabel(entry, t);
  const isFeature = variant === "feature";

  return (
    <li className={isFeature ? styles.resumeItemFeature : styles.resumeItem}>
      {/* The thumbnail is a link only to the title page; the launch action is
          the explicit play button, per the resume audit, not a poster hover. */}
      <Link
        className={styles.continueThumb}
        href={`/titles/${title.slug}`}
        title={title.name}
      >
        {title.poster_url ? (
          <Image
            className={styles.continueThumbArt}
            src={title.poster_url}
            alt=""
            fill
            sizes={isFeature ? "(max-width: 767px) 128px, 176px" : "(max-width: 767px) 88px, 128px"}
            quality={92}
            referrerPolicy="no-referrer"
          />
        ) : (
          <span className={styles.continueFallback} aria-hidden="true">
            {title.name.slice(0, 1).toUpperCase()}
          </span>
        )}
      </Link>
      <div className={styles.continueBody}>
        <Link className={styles.continueTitle} href={`/titles/${title.slug}`}>{title.name}</Link>
        <span className={styles.continueFact}>{factLine}</span>
        {countLine !== "" && <span className={styles.continueMeta}>{countLine}</span>}
        {voiceLine !== "" && <span className={styles.continueVoice}>{voiceLine}</span>}
        {/* No track without a started episode: an empty bar under "Смотреть
            серию N" reads as lost progress rather than as a fresh episode. */}
        {started && (
          <span className={styles.continueProgressTrack} aria-hidden="true">
            <span className={styles.continueProgressBar} style={{ width: `${resumeProgressPercent(entry)}%` }} />
          </span>
        )}
      </div>
      <div className={styles.continueActions}>
        <Link className={`primary ${styles.continuePlay}`} href={playHref}>
          <Play aria-hidden="true" weight="fill" size={16} />
          {playLabel}
        </Link>
        {onRemoved && <ContinueMenu entry={entry} onRemoved={onRemoved} />}
      </div>
    </li>
  );
}

/** Guest hero: one welcome card, no progress data, points at the catalog. */
function GuestHero({ featured }: { featured?: CatalogItem }) {
  const { t } = useI18n();
  const href = featured?.episodes_count ? titleWatchHref(featured.slug) : "/catalog";
  return (
    <section className={styles.resumeHero} aria-label={t("home.heroEyebrow")}>
      {featured?.poster_url ? (
        <div className={styles.resumeHeroBackdrop} aria-hidden="true">
          <Image
            className={styles.resumeHeroBackdropArt}
            src={featured.poster_url}
            alt=""
            fill
            sizes="(max-width: 520px) 100vw, (max-width: 1199px) 72vw, 66vw"
            quality={92}
            referrerPolicy="no-referrer"
          />
        </div>
      ) : null}
      <div className={styles.resumeHeroArtFrame} aria-hidden="true">
        {featured?.poster_url ? (
          <Image
            className={styles.resumeHeroArt}
            src={featured.poster_url}
            alt=""
            fill
            sizes="(max-width: 520px) 92px, 176px"
            quality={92}
            referrerPolicy="no-referrer"
          />
        ) : null}
      </div>
      <div className={styles.resumeHeroBody}>
        <p className={styles.resumeHeroEyebrow}>{t("home.heroEyebrow")}</p>
        <h1 className={styles.resumeHeroTitle}>{t("home.title")}</h1>
        <p className={styles.heroSynopsis}>{featured?.synopsis ?? t("home.subtitle")}</p>
        <div className={styles.resumeHeroActions}>
          <Link className={`primary inline-button ${styles.resumeHeroCta}`} href={href}>
            <Play aria-hidden="true" weight="fill" size={19} />
            {t("home.openCatalog")}
          </Link>
          <Link className={`secondary inline-button ${styles.resumeHeroSecondary}`} href="/register">
            {t("nav.register")}
          </Link>
        </div>
      </div>
    </section>
  );
}

/**
 * Home opening block: one shelf, the freshest entry featured as a compact
 * horizontal card (small cover, name, fact, voice, explicit launch, ⋯ menu),
 * the rest as rows below it. No duplicated giant banner, no synopsis in the
 * continuation — those live on the title page.
 */
export function ContinueWatchingBlock({ catalogCount, featured }: { catalogCount?: number; featured?: CatalogItem }) {
  const { t } = useI18n();
  const state = useContinueWatching();
  const [removed, setRemoved] = useState<string[]>([]);

  if (state.kind === "loading") return null;
  if (state.kind === "guest") {
    return (
      <>
        <GuestHero featured={featured} />
        {typeof catalogCount === "number" && catalogCount > 0 && (
          <p className={styles.catalogFact}>{t("home.catalogCount", { count: catalogCount })}</p>
        )}
      </>
    );
  }
  if (state.kind === "error") return null;

  const entries = state.entries
    .filter((entry) => !removed.includes(entry.title.slug))
    .slice(0, VISIBLE_LIMIT);
  // A signed-in viewer with nothing in progress gets the shelves below; the
  // guest hero with its register link is for guests only.
  if (entries.length === 0) return null;

  const [first, ...rest] = entries;
  return (
    <section className={styles.continueSection} aria-label={t("home.continueWatching")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.continueWatching")}</h2>
          <p>{t("home.continueWatchingText")}</p>
        </div>
        <Link href="/history">{t("home.allStarted")}</Link>
      </div>
      <ul className={styles.continueList}>
        <ResumeCard entry={first} variant="feature" onRemoved={(slug) => setRemoved((value) => [...value, slug])} />
        {rest.map((entry) => (
          <ResumeCard entry={entry} key={entry.title.slug} onRemoved={(slug) => setRemoved((value) => [...value, slug])} />
        ))}
      </ul>
    </section>
  );
}

/** Account-hub variant: rows-only, silent when there is nothing. */
export function ResumeShelf() {
  const { t } = useI18n();
  const state = useContinueWatching();
  const [removed, setRemoved] = useState<string[]>([]);
  if (state.kind !== "ready" || state.entries.length === 0) return null;
  const entries = state.entries
    .filter((entry) => !removed.includes(entry.title.slug))
    .slice(0, VISIBLE_LIMIT);
  if (entries.length === 0) return null;
  return (
    <section className={styles.continueSection} aria-label={t("home.continueWatching")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.continueWatching")}</h2>
        </div>
        <Link href="/history">{t("home.allStarted")}</Link>
      </div>
      <ul className={styles.continueList}>
        {entries.map((entry, index) => (
          <ResumeCard
            entry={entry}
            key={entry.title.slug}
            variant={index === 0 ? "feature" : "row"}
            onRemoved={(slug) => setRemoved((value) => [...value, slug])}
          />
        ))}
      </ul>
    </section>
  );
}
