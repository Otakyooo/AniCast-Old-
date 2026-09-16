"use client";

import Image from "next/image";
import Link from "next/link";
import { CaretLeft, CaretRight, DotsThree, Play } from "@phosphor-icons/react";
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

/** The rail carries up to twelve entries; the viewport shows what fits and the
 *  arrows reveal the rest. Six would leave the arrows dead on a wide screen. */
const VISIBLE_LIMIT = 12;
const SKELETON_COUNT = 5;

/** Card geometry from the spec (§48): 190px cards on a 14px gutter. One arrow
 *  step is three cards, or 80% of the visible rail on narrow screens. */
const CARD_WIDTH = 190;
const CARD_GAP = 14;

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
    <div className={styles.continueMenuWrap} ref={containerRef}>
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

/**
 * One rail card: poster first, then the title, then the state line.
 *
 * The watch action is an *overlay* link, not a wrapper. The card also carries a
 * title link and a menu button, and nesting interactive elements inside an
 * anchor is invalid HTML and breaks keyboard navigation (§33). The overlay sits
 * above the artwork, the title and the menu are lifted above it with z-index,
 * and the tab order stays watch → title → menu per card.
 *
 * Two states only. An episode in progress shows the bar and "Осталось N мин";
 * a finished one points at the next episode and shows no bar at all, because a
 * zero-width bar is a lie about progress that has not been made.
 */
function ContinueCard({
  entry,
  onRemoved,
}: {
  entry: ContinueWatchingEntry;
  onRemoved?: (slug: string) => void;
}) {
  const { t } = useI18n();
  const target = resumeEpisode(entry);
  if (!target) return null;

  const title = entry.title;
  const isResume = resumeEpisodeStarted(entry);
  const titleHref = `/titles/${title.slug}`;
  const playHref = titleWatchHref(title.slug, target.number, entry.source_selection_key || undefined);
  const watchAria = isResume
    ? t("home.resumeCtaAria", { name: title.name, number: target.number })
    : t("home.watchCtaAria", { name: title.name, number: target.number });
  const percent = isResume ? resumeProgressPercent(entry) : 0;
  const remaining = isResume ? formatRemaining(remainingSeconds(entry), t) : "";

  return (
    <li className={styles.continueCard}>
      <Link className={styles.continueWatch} href={playHref} aria-label={watchAria} />
      <span className={styles.continuePoster}>
        {title.poster_url ? (
          <Image
            className={styles.continuePosterArt}
            src={title.poster_url}
            alt=""
            fill
            sizes="190px"
            quality={80}
            referrerPolicy="no-referrer"
          />
        ) : (
          <span className={styles.continuePosterFallback} aria-hidden="true">
            {title.name.slice(0, 1).toUpperCase()}
          </span>
        )}
        <span className={styles.continuePlayBadge} aria-hidden="true">
          <Play weight="fill" size={18} />
        </span>
      </span>
      <span className={styles.continueBody}>
        <Link className={styles.continueTitle} href={titleHref}>{title.name}</Link>
        <span className={styles.continueMetaLine}>
          {t("home.episodeMeta", { number: target.number })}
        </span>
        {isResume && (
          <span className={styles.continueTrack} aria-hidden="true">
            <span className={styles.continueFill} style={{ width: `${percent}%` }} />
          </span>
        )}
        <span className={styles.continueNote}>
          {isResume ? remaining : t("home.nextEpisodeLabel")}
        </span>
      </span>
      {onRemoved && <ContinueMenu entry={entry} onRemoved={onRemoved} />}
    </li>
  );
}

/**
 * Heading, arrows and rail for one shelf of resume cards.
 *
 * The arrows come before "Все →" in the DOM so the keyboard order is
 * ← → Все → card 1 → card 2 …, matching the visual reading order.
 */
function ContinueShelf({
  entries,
  onRemoved,
}: {
  entries: ContinueWatchingEntry[];
  onRemoved?: (slug: string) => void;
}) {
  const { t } = useI18n();
  const railRef = useRef<HTMLUListElement>(null);
  const [edges, setEdges] = useState({ start: true, end: true });

  const sync = useCallback(() => {
    const rail = railRef.current;
    if (!rail) return;
    const max = rail.scrollWidth - rail.clientWidth;
    // 2px of slack: fractional layout widths otherwise leave an arrow enabled
    // at the very end with nothing left to scroll.
    setEdges({ start: rail.scrollLeft <= 2, end: max <= 2 || rail.scrollLeft >= max - 2 });
  }, []);

  useEffect(() => {
    const rail = railRef.current;
    if (!rail) return;
    sync();
    rail.addEventListener("scroll", sync, { passive: true });
    const observer = new ResizeObserver(sync);
    observer.observe(rail);
    return () => {
      rail.removeEventListener("scroll", sync);
      observer.disconnect();
    };
  }, [sync, entries.length]);

  function step(direction: -1 | 1) {
    const rail = railRef.current;
    if (!rail) return;
    const distance = Math.min(rail.clientWidth * 0.8, CARD_WIDTH * 3 + CARD_GAP * 2);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    rail.scrollBy({ left: direction * distance, behavior: reduced ? "auto" : "smooth" });
  }

  return (
    <section className={styles.continueSection} aria-label={t("home.continueWatching")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.continueWatching")}</h2>
        </div>
        <div className={styles.continueHeadingActions}>
          <button
            type="button"
            className={styles.continueArrow}
            aria-label={t("rail.scrollBack")}
            disabled={edges.start}
            onClick={() => step(-1)}
          >
            <CaretLeft aria-hidden="true" size={18} weight="bold" />
          </button>
          <button
            type="button"
            className={styles.continueArrow}
            aria-label={t("rail.scrollForward")}
            disabled={edges.end}
            onClick={() => step(1)}
          >
            <CaretRight aria-hidden="true" size={18} weight="bold" />
          </button>
          <Link href="/history">{t("home.continueAll")}</Link>
        </div>
      </div>
      <ul className={styles.continueRail} ref={railRef}>
        {entries.map((entry) => (
          <ContinueCard entry={entry} key={entry.title.slug} onRemoved={onRemoved} />
        ))}
      </ul>
    </section>
  );
}

/** Placeholder rail sized like the real block so the page does not jump. */
function ContinueSkeleton() {
  const { t } = useI18n();
  return (
    <section className={styles.continueSection} aria-hidden="true">
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.continueWatching")}</h2>
        </div>
      </div>
      <ul className={styles.continueRail}>
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
 * Home opening block: one horizontal rail of resume cards, newest activity
 * first. The poster is the visual anchor, there is no persistent CTA on any
 * card, and the section is hidden outright when there is nothing to resume --
 * an error must never hold up the rest of the page.
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

  const entries = state.entries
    .filter((entry) => !removed.includes(entry.title.slug))
    .slice(0, VISIBLE_LIMIT);
  if (entries.length === 0) return null;

  return (
    <>
      <ContinueShelf
        entries={entries}
        onRemoved={(slug) => {
          setRemoved((value) => [...value, slug]);
          setUndoSlug(slug);
        }}
      />
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
    </>
  );
}

/** Account-hub variant: the same rail, silent when there is nothing. */
export function ResumeShelf() {
  const state = useContinueWatching();
  const [removed, setRemoved] = useState<string[]>([]);
  if (state.kind !== "ready" || state.entries.length === 0) return null;
  const entries = state.entries
    .filter((entry) => !removed.includes(entry.title.slug))
    .slice(0, VISIBLE_LIMIT);
  if (entries.length === 0) return null;
  return (
    <ContinueShelf entries={entries} onRemoved={(slug) => setRemoved((value) => [...value, slug])} />
  );
}
