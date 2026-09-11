"use client";

import Link from "next/link";
import { Plus, Check } from "@phosphor-icons/react";
import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";
import type { CatalogItem } from "../lib/api";
import { episodeCountLabel } from "../lib/episode-count";
import { titleRating } from "../lib/rating";
import { informativeTitleType, titleTemplateState } from "../lib/title-template";
import {
  applyLibraryStatusLocally,
  useCardLibraryEntry,
} from "../lib/library-statuses";
import { putLibraryEntry, deleteLibraryEntry, type LibraryStatus } from "../lib/library";
import { useI18n } from "./i18n-provider";

const LIBRARY_OPTIONS: Array<{ value: LibraryStatus; labelKey: string }> = [
  { value: "planned", labelKey: "nav.planned" },
  { value: "watching", labelKey: "nav.watching" },
  { value: "completed", labelKey: "nav.completed" },
  { value: "on_hold", labelKey: "library.onHold" },
  { value: "dropped", labelKey: "library.dropped" },
];

const STATUS_LABEL_KEY: Record<LibraryStatus, string> = {
  planned: "nav.planned",
  watching: "nav.watching",
  completed: "nav.completed",
  on_hold: "library.onHold",
  dropped: "library.dropped",
};

function formatVoice(_label: string, value: string) {
  return `${_label}: ${value}`;
}

/** Release state line: when the list doesn't annotate playability (nil), the
 *  release status text is the honest fallback instead of a count we cannot
 *  promise. */
function releaseAndAvailabilityLine(
  item: CatalogItem,
  t: (key: string, values?: Record<string, string | number>) => string,
): string | null {
  const playable = item.playable_episodes_count;
  const total = item.episodes_count;
  if (typeof playable === "number") {
    if (playable > 0) {
      return typeof total === "number" && total > 0
        ? item.status === "ongoing"
          ? t("card.playableOfOngoing", { available: playable, total })
          : t("card.playableOf", { available: playable, total })
        : t("card.playableOnly", { available: playable });
    }
    return t("card.noPlayable");
  }
  // Unannotated contexts (search, similar titles): fall back to the release
  // status only, never a made-up playability number.
  return item.status ? t(`status.${item.status}`) : null;
}

/** Library chip + menu on a catalog card: "" means the title is not in the
 *  list; the menu offers the full status set plus removal. Guests see nothing:
 *  a disabled action reads as a lane that is broken. */
function CardLibraryControls({ slug }: { slug: string }) {
  const { t } = useI18n();
  const { entry, ready, guest } = useCardLibraryEntry(slug);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  // useId keeps the menu id stable across renders and SSR-safe.
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!ready || guest) {
    // Loading: reserved height avoids a layout jump when the statuses arrive.
    // Guests see nothing and reach the same actions from title pages instead.
    return <span className="card-library-loader" aria-hidden="true" />;
  }

  async function apply(status: LibraryStatus | null) {
    setPending(true);
    setError("");
    const previous = entry;
    try {
      if (status === null) {
        await deleteLibraryEntry(slug);
        applyLibraryStatusLocally(slug, null);
      } else {
        await putLibraryEntry(slug, { status, is_favorite: previous?.is_favorite ?? false });
        applyLibraryStatusLocally(slug, { status, is_favorite: previous?.is_favorite ?? false });
      }
      setOpen(false);
    } catch {
      setError(t("common.error"));
    } finally {
      setPending(false);
    }
  }

  const activeLabel = entry ? t(STATUS_LABEL_KEY[entry.status]) : t("card.addToLibrary");

  return (
    <div className="card-library" ref={containerRef}>
      {entry ? (
        <button
          type="button"
          className="card-library-chip"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={open ? menuId : undefined}
          title={activeLabel}
          onClick={() => setOpen((value) => !value)}
        >
          <Check aria-hidden="true" weight="bold" size={12} />
          {activeLabel}
        </button>
      ) : (
        <button
          type="button"
          className="card-library-add"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={open ? menuId : undefined}
          onClick={() => setOpen((value) => !value)}
        >
          <Plus aria-hidden="true" size={13} weight="bold" />
          {t("card.addToLibrary")}
        </button>
      )}
      {open && (
        <div className="card-library-menu" id={menuId} role="menu">
          {LIBRARY_OPTIONS.map((option) => {
            const isActive = entry?.status === option.value;
            return (
              <button
                key={option.value}
                type="button"
                role="menuitemradio"
                aria-checked={isActive}
                className={isActive ? "card-library-choice is-active" : "card-library-choice"}
                onClick={() => void apply(option.value)}
              >
                {t(option.labelKey)}
                {isActive && <Check aria-hidden="true" weight="bold" size={11} />}
              </button>
            );
          })}
          {entry && (
            <button
              type="button"
              role="menuitem"
              className="card-library-choice card-library-remove"
              onClick={() => void apply(null)}
            >
              {t("card.removeFromLibrary")}
            </button>
          )}
          {error && <p className="card-library-hint" role="alert">{error}</p>}
        </div>
      )}
    </div>
  );
}

export function CatalogCard({ item, variant = "default" }: { item: CatalogItem; variant?: "default" | "media" }) {
  const { t, locale } = useI18n();
  const rating = titleRating(item);
  const typeLabel = informativeTitleType(item.title_type) ? t(`type.${item.title_type}`) : null;
  const episodesLabel = titleTemplateState(item.title_type, item.episodes_count).showEpisodeCount
    && typeof item.episodes_count === "number"
    ? episodeCountLabel(t, locale, item.episodes_count)
    : null;
  // Row 1: the honest facts — year, type and catalogue episode total.
  const facts = [item.year ?? null, typeLabel, episodesLabel]
    .filter((value): value is string | number => value !== null && value !== undefined)
    .join(" · ");
  const genreLine = (item.genres ?? []).slice(0, 2).map((genre) => genre.name).join(", ");
  const availabilityLine = releaseAndAvailabilityLine(item, t);

  return (
    <div className={`catalog-card ${variant === "media" ? "catalog-card-media" : ""}`}>
      <Link className="catalog-card-main" href={`/titles/${item.slug}`} title={item.name}>
        <div className="poster-wrap">
          {item.poster_url ? (
            <Image
              className="poster-image"
              src={item.poster_url}
              alt=""
              fill
              quality={92}
              sizes={variant === "media" ? "(max-width: 768px) 42vw, 176px" : "(max-width: 768px) 50vw, 220px"}
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="poster-placeholder" style={{ "--poster-accent": "#6d5dfb" } as React.CSSProperties} aria-hidden="true">
              <span>{item.name.slice(0, 1).toUpperCase()}</span>
            </div>
          )}
          {rating && (
            // Numeric-only tooltip keeps every locale free of plural forms.
            <span className="card-rating" title={`${rating.average} / 10 · ${rating.count}`}>
              ★ {rating.average}
            </span>
          )}
        </div>
        <div className="catalog-card-body">
          {/* Headline first; the old upper-accent kicker said only the release
              status. Remove it — the availability line below carries it. */}
          <h2 title={item.name}>{item.name}</h2>
          <p>{facts}</p>
          {genreLine && <small className="card-genres">{genreLine}</small>}
          {availabilityLine && <small className="card-availability">{availabilityLine}</small>}
        </div>
      </Link>
      {/* Library toggle: visible even on hover-free pointers, outside the
          click area of the card link itself. */}
      <CardLibraryControls slug={item.slug} />
    </div>
  );
}
