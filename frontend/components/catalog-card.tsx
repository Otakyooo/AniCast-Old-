"use client";

import Image from "next/image";
import Link from "next/link";
import type { CatalogItem } from "../lib/api";
import { titleRating } from "../lib/rating";
import { useI18n } from "./i18n-provider";

export function CatalogCard({ item, variant = "default" }: { item: CatalogItem; variant?: "default" | "media" }) {
  const { t } = useI18n();
  const status = item.status ? t(`status.${item.status}`) : t("type.anime");
  const rating = titleRating(item);

  return (
    <Link className={`catalog-card ${variant === "media" ? "catalog-card-media" : ""}`} href={`/titles/${item.slug}`}>
      <div className="poster-wrap">
        {item.poster_url ? (
          <Image
            className="poster-image"
            src={item.poster_url}
            alt=""
            fill
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
        <h2>{item.name}</h2>
        <p>{item.year ?? t("year.unknown")}{item.title_type ? ` · ${t(`type.${item.title_type}`)}` : ""}</p>
      </div>
    </Link>
  );
}
