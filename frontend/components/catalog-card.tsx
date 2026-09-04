"use client";

import Image from "next/image";
import Link from "next/link";
import type { CatalogItem } from "../lib/api";
import { episodeCountLabel } from "../lib/episode-count";
import { titleRating } from "../lib/rating";
import { informativeTitleType, titleTemplateState } from "../lib/title-template";
import { useI18n } from "./i18n-provider";

export function CatalogCard({ item, variant = "default" }: { item: CatalogItem; variant?: "default" | "media" }) {
  const { t, locale } = useI18n();
  const status = item.status ? t(`status.${item.status}`) : t("type.anime");
  const rating = titleRating(item);
  // Shelf and grid cards carry one compact fact line: release year, title type
  // and the real episode total from the list payload. The default "anime"
  // label says nothing on an anime service, and movies never have episodes,
  // so both stay hidden instead of producing "Фильм · 1 серия".
  const facts = [
    item.year ?? t("year.unknown"),
    informativeTitleType(item.title_type) ? t(`type.${item.title_type}`) : null,
    titleTemplateState(item.title_type, item.episodes_count).showEpisodeCount
      && typeof item.episodes_count === "number"
      ? episodeCountLabel(t, locale, item.episodes_count)
      : null,
  ].filter(Boolean).join(" · ");

  return (
    <Link className={`catalog-card ${variant === "media" ? "catalog-card-media" : ""}`} href={`/titles/${item.slug}`}>
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
          <div
            className="poster-placeholder"
            style={{ "--poster-accent": "#6d5dfb" } as React.CSSProperties}
            aria-hidden="true"
          >
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
        <span className="card-kicker">{status}</span>
        {/* Clamped titles need an accessible way to read the full name. */}
        <h2 title={item.name}>{item.name}</h2>
        <p title={facts}>{facts}</p>
      </div>
    </Link>
  );
}
