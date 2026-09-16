"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DotsThree, Play } from "@phosphor-icons/react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { CatalogItem } from "../lib/api";
import {
  ContinueWatchingApiError,
  formatRemaining,
  getContinueWatching,
  hideFromContinueWatching,
  remainingSeconds,
  resetEpisodeProgress,
  resumeEpisode,
  resumeEpisodeStarted,
  resumeProgressPercent,
  unhideFromContinueWatching,
  type ContinueWatchingEntry,
} from "../lib/continue-watching";
import { titleWatchHref } from "../lib/seo";
import { useI18n } from "./i18n-provider";
import styles from "../app/home.module.css";

/** Six cards fill three compact rows of two; the rest live behind "Все →". */
const VISIBLE_LIMIT = 6;
const SKELETON_COUNT = 4;

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

/** ⋯ menu: restart the episode (with a confirm) or drop the title from this
 *  shelf. Hiding never touches the library entry or the watch history. */
function ContinueMenu({
  entry,
  onRemoved,
}: {
  entry: ContinueWatchingEntry;
  onRemoved: (slug: string) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const menuId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const target = resumeEpisode(entry);

  const close = useCallback(() => {
    setOpen(false);
    setConfirming(false);
  }, []);

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

  async function restart() {
    if (!target) return;
    setPending(true);
    setError("");
    try {
      await resetEpisodeProgress(entry.title.slug, target.number, entry.duration_seconds ?? 0);
      close();
    } catch {
      setError(t("common.error"));
    } finally {
      setPending(false);
    }
  }

  async function hide() {
    setPending(true);
    setError("");
    try {
      await hideFromContinueWatching(entry.title.slug);
      close();
      onRemoved(entry.title.slug);
    } catch {
      setError(t("common.error"));
    } finally {
      setPending(false);
    }
  }

  return (
    // The menu sits inside a clickable card: without this the card navigation
    // fires on every menu interaction.
    <div
      className={styles.continueMenuWrap}
      ref={containerRef}
      onClick={(event) => event.stopPropagation()}
    >
      <button
        ref={triggerRef}
        className={styles.continueMenuButton}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={t("home.menuAria", { name: entry.title.name })}
        onClick={() => {
          setOpen((value) => !value);
          setConfirming(false);
        }}
      >
        <DotsThree aria-hidden="true" size={18} weight="bold" />
      </button>
      {open && (
        <div className={styles.continueMenu} id={menuId} role="menu">
          {confirming ? (
            <div className={styles.continueConfirm}>
              <strong>{t("home.restartQuestion")}</strong>
              <span>{t("home.restartWarning")}</span>
              <div className={styles.continueConfirmActions}>
                <button
                  type="button"
                  className={styles.continueConfirmCancel}
                  disabled={pending}
                  onClick={() => setConfirming(false)}
                >
                  {t("home.cancel")}
                </button>
                <button
                  type="button"
                  className={styles.continueConfirmDo}
                  disabled={pending}
                  onClick={() => void restart()}
                >
                  {t("home.restartConfirm")}
                </button>
              </div>
            </div>
          ) : (
            <>
              <button
                type="button"
                role="menuitem"
                className={styles.continueMenuChoice}
                disabled={pending || !target}
                onClick={() => setConfirming(true)}
              >
                {t("home.restartEpisode")}
              </button>
              <button
                type="button"
                role="menuitem"
                className={styles.continueMenuChoice}
                disabled={pending}
                onClick={() => void hide()}
              >
                {t("home.removeFromContinue")}
              </button>
            </>
          )}
          {error && <span className={styles.continueMenuError} role="alert">{error}</span>}
        </div>
      )}
    </div>
  );
}

/** One compact resume card. Two states only: an episode in progress shows the
 *  bar and "Осталось N мин"; a finished one points at the next episode without
 *  a fake zero-width bar. The episode number appears once, in the meta line --
 *  never again in the CTA. */
export function ResumeCard({
  entry,
  onRemoved,
}: {
  entry: ContinueWatchingEntry;
  onRemoved?: (slug: string) => void;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const target = resumeEpisode(entry);
  if (!target) return null;

  const title = entry.title;
  const isResume = resumeEpisodeStarted(entry);
  const titleHref = `/titles/${title.slug}`;
  const playHref = titleWatchHref(title.slug, target.number, entry.source_selection_key || undefined);
  const ctaLabel = isResume ? t("home.resumeCta") : t("home.watchCta");
  const ctaAria = isResume
    ? t("home.resumeCtaAria", { name: title.name, number: target.number })
    : t("home.watchCtaAria", { name: title.name, number: target.number });
  const percent = isResume ? resumeProgressPercent(entry) : 0;
  const remaining = isResume ? formatRemaining(remainingSeconds(entry), t) : "";

  return (
    <li className={styles.continueCard} onClick={() => router.push(titleHref)}>
      {/* The poster duplicates the title link for pointer users; tabIndex -1
          keeps it out of the keyboard order so the title stays the one stop. */}
      <Link
        className={styles.continuePoster}
        href={titleHref}
        tabIndex={-1}
        aria-hidden="true"
        onClick={(event) => event.stopPropagation()}
      >
        {title.poster_url ? (
          <Image
            className={styles.continuePosterArt}
            src={title.poster_url}
            alt=""
            fill
            sizes="64px"
            quality={80}
            referrerPolicy="no-referrer"
          />
        ) : (
          <span className={styles.continuePosterFallback} aria-hidden="true">
            {title.name.slice(0, 1).toUpperCase()}
          </span>
        )}
      </Link>
      <div className={styles.continueCardBody}>
        <div className={styles.continueTop}>
          <Link
            className={styles.continueTitle}
            href={titleHref}
            onClick={(event) => event.stopPropagation()}
          >
            {title.name}
          </Link>
          {onRemoved && <ContinueMenu entry={entry} onRemoved={onRemoved} />}
        </div>
        <span className={styles.continueMetaLine}>
          {t("home.episodeMeta", { number: target.number })}
        </span>
        {isResume && (
          <span className={styles.continueTrack} aria-hidden="true">
            <span className={styles.continueFill} style={{ width: `${percent}%` }} />
          </span>
        )}
        <div className={styles.continueBottom}>
          <span className={styles.continueNote}>
            {isResume ? remaining : t("home.nextEpisodeLabel")}
          </span>
          <Link
            className={styles.continueCta}
            href={playHref}
            aria-label={ctaAria}
            onClick={(event) => event.stopPropagation()}
          >
            <Play aria-hidden="true" weight="fill" size={14} />
            {ctaLabel}
          </Link>
        </div>
      </div>
    </li>
  );
}

/** Placeholder grid sized like the real block so the page does not jump. */
function ContinueSkeleton() {
  return (
    <section className={styles.continueSection} aria-hidden="true">
      <ul className={styles.continueList}>
        {Array.from({ length: SKELETON_COUNT }, (_, index) => (
          <li key={index} className={`${styles.continueCard} ${styles.continueCardSkeleton}`}>
            <span className={styles.continueSkeletonPoster} />
            <span className={styles.continueSkeletonBody}>
              <span className={styles.continueSkeletonLine} />
              <span className={`${styles.continueSkeletonLine} ${styles.continueSkeletonLineShort}`} />
            </span>
          </li>
        ))}
      </ul>
    </section>
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
 * Home opening block: a compact two-column grid of resume cards, at most six,
 * newest activity first. No giant featured card, no per-card synopsis, and the
 * section is hidden outright when there is nothing to resume -- an error must
 * never hold up the rest of the page.
 */
export function ContinueWatchingBlock({ catalogCount, featured }: { catalogCount?: number; featured?: CatalogItem }) {
  const { t } = useI18n();
  const state = useContinueWatching();
  const [removed, setRemoved] = useState<string[]>([]);
  const [undoSlug, setUndoSlug] = useState<string | null>(null);

  if (state.kind === "loading") return <ContinueSkeleton />;
  if (state.kind === "error") return null;
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

  const entries = state.entries.filter((entry) => !removed.includes(entry.title.slug));
  if (entries.length === 0) return null;

  const visible = entries.slice(0, VISIBLE_LIMIT);

  return (
    <section className={styles.continueSection} aria-label={t("home.continueWatching")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.continueWatching")}</h2>
        </div>
        <Link href="/history">{t("home.continueAll")}</Link>
      </div>
      <ul className={styles.continueList}>
        {visible.map((entry) => (
          <ResumeCard
            entry={entry}
            key={entry.title.slug}
            onRemoved={(slug) => {
              setRemoved((value) => [...value, slug]);
              setUndoSlug(slug);
            }}
          />
        ))}
      </ul>
      {undoSlug && (
        <div className={styles.continueToast} role="status">
          <span>{t("home.continueRemoved")}</span>
          <button
            type="button"
            onClick={() => {
              void unhideFromContinueWatching(undoSlug);
              setRemoved((value) => value.filter((slug) => slug !== undoSlug));
              setUndoSlug(null);
            }}
          >
            {t("home.undo")}
          </button>
        </div>
      )}
    </section>
  );
}

/** Account-hub variant: the same compact cards, silent when there is nothing. */
export function ResumeShelf() {
  const { t } = useI18n();
  const state = useContinueWatching();
  const [removed, setRemoved] = useState<string[]>([]);
  if (state.kind !== "ready" || state.entries.length === 0) return null;
  const entries = state.entries.filter((entry) => !removed.includes(entry.title.slug));
  if (entries.length === 0) return null;
  return (
    <section className={styles.continueSection} aria-label={t("home.continueWatching")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.continueWatching")}</h2>
        </div>
        <Link href="/history">{t("home.continueAll")}</Link>
      </div>
      <ul className={styles.continueList}>
        {entries.map((entry) => (
          <ResumeCard
            entry={entry}
            key={entry.title.slug}
            onRemoved={(slug) => setRemoved((value) => [...value, slug])}
          />
        ))}
      </ul>
    </section>
  );
}
