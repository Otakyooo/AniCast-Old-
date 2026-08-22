"use client";

import Image from "next/image";
import Link from "next/link";
import type { CatalogItem } from "../lib/api";
import { useI18n } from "./i18n-provider";

export function CatalogCard({ item }: { item: CatalogItem }) {
  const { t } = useI18n();
  const status = item.status ? t(`status.${item.status}`) : t("type.anime");

  return (
    <Link className="catalog-card" href={`/titles/${item.slug}`}>
      <div className="poster-wrap">
        {item.poster_url ? (
          <Image
            className="poster-image"
            src={item.poster_url}
            alt=""
            fill
            sizes="(max-width: 768px) 50vw, 220px"
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
      </div>
      <div className="catalog-card-body">
        <span className="card-kicker">{status}</span>
        <h2>{item.name}</h2>
        <p>{item.year ?? t("year.unknown")}{item.title_type ? ` · ${t(`type.${item.title_type}`)}` : ""}</p>
      </div>
    </Link>
  );
}
