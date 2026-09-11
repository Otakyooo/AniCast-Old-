"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CatalogCard } from "./catalog-card";
import { getAiringTitles, type CatalogItem } from "../lib/api";
import { getLibrary } from "../lib/library";
import { useI18n } from "./i18n-provider";
import styles from "../app/profile.module.css";

const SHELF_LIMIT = 6;

function isAbort(reason: unknown): boolean {
  return reason instanceof DOMException && reason.name === "AbortError";
}

function softFail(reason: unknown): CatalogItem[] {
  if (isAbort(reason)) throw reason;
  return [];
}

type Shelf = {
  heading: string;
  href?: string;
  items: CatalogItem[];
};

export default function LibraryStatusShelves() {
  const { t } = useI18n();
  const [shelves, setShelves] = useState<Shelf[] | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    Promise.all([
      getLibrary({ status: "watching", page_size: SHELF_LIMIT }, signal)
        .then((page) => page.results.map((entry) => entry.title))
        .catch(softFail),
      getLibrary({ status: "planned", page_size: SHELF_LIMIT }, signal)
        .then((page) => page.results.map((entry) => entry.title))
        .catch(softFail),
      getAiringTitles(signal).catch(softFail),
    ])
      .then(([watching, planned, airing]) => {
        const watchingSlugs = new Set(watching.map((item) => item.slug));
        const nextAt = (item: CatalogItem) => {
          const time = item.next_episode_at ? Date.parse(item.next_episode_at) : Number.NaN;
          return Number.isNaN(time) ? Number.POSITIVE_INFINITY : time;
        };
        const newEpisodes = airing
          .filter((item) => watchingSlugs.has(item.slug))
          .sort((a, b) => nextAt(a) - nextAt(b))
          .slice(0, SHELF_LIMIT);

        setShelves([
          { heading: t("account.watchingHeading"), href: "/library?status=watching", items: watching },
          { heading: t("account.plannedHeading"), href: "/library?status=planned", items: planned },
          { heading: t("account.newEpisodesHeading"), items: newEpisodes },
        ]);
      })
      .catch((reason: unknown) => {
        if (isAbort(reason)) return;
        setShelves([]);
      });

    return () => controller.abort();
  }, [t]);

  if (!shelves) return null;

  const visible = shelves.filter((shelf) => shelf.items.length > 0);
  if (visible.length === 0) return null;

  return (
    <>
      {visible.map((shelf) => (
        <section aria-label={shelf.heading} key={shelf.heading}>
          <div className={styles.notesHeading}>
            <h2>{shelf.heading}</h2>
            {shelf.href && <Link href={shelf.href}>{t("home.showAll")}</Link>}
          </div>
          <div className="catalog-grid">
            {shelf.items.map((item) => (
              <CatalogCard item={item} key={item.slug} />
            ))}
          </div>
        </section>
      ))}
    </>
  );
}
